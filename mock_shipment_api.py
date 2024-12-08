from flask import Flask, request, jsonify
import sqlite3
import random
import datetime
import logging

# Set up application
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)


def get_db():
    try:
        db = sqlite3.connect('penta_book.db')  # Ensure the path is correct
        db.row_factory = sqlite3.Row
        return db
    except sqlite3.Error as e:
        logging.error(f"Database connection failed: {e}")
        raise


@app.route('/initiate_shipment', methods=['POST'])
def initiate_shipment():
    data = request.json

    if not data or 'order_id' not in data:
        return jsonify({'status': 'error', 'message': 'Order ID is required.'}), 400

    order_id = data.get('order_id')
    shipment_service = data.get('shipment_service', 'default_service')

    db = get_db()
    try:
        # Check if the order exists
        order = db.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)).fetchone()
        if not order:
            return jsonify({'status': 'error', 'message': 'Order not found.'}), 404

        # Generate a mock tracking number
        tracking_no = 'TRK' + str(random.randint(100000, 999999))

        # Create shipment entry
        db.execute('''
            INSERT INTO shipment (order_id, tracking_no, shipment_date, status, shipment_service)
            VALUES (?, ?, ?, ?, ?)
        ''', (order_id, tracking_no, datetime.datetime.now().isoformat(), 'Shipped', shipment_service))
        db.commit()
        db.execute('''
            INSERT INTO orders (status)
            VALUES (?)
            ''', 'Shipped')
        db.commit()

        logging.info(f"Shipment initiated for order {order_id} with tracking number {tracking_no}.")
        return jsonify({'status': 'success', 'tracking_no': tracking_no}), 201
    except sqlite3.Error as e:
        logging.error(f"SQL error: {e}")
        return jsonify({'status': 'error', 'message': 'Database error occurred.'}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred.'}), 500
    finally:
        if db:
            db.close()


@app.route('/track_shipment/<tracking_no>', methods=['GET'])
def track_shipment(tracking_no):
    db = get_db()
    try:
        shipment = db.execute('SELECT * FROM shipment WHERE tracking_no = ?', (tracking_no,)).fetchone()
        if not shipment:
            return jsonify({'status': 'error', 'message': 'Shipment not found.'}), 404

        shipment_data = {
            'tracking_no': shipment['tracking_no'],
            'order_id': shipment['order_id'],
            'shipment_date': shipment['shipment_date'],
            'received_date': shipment['received_date'] or 'Not received yet',  # Handle null values
            'status': shipment['status'],
            'shipment_service': shipment['shipment_service']
        }

        logging.info(f"Shipment tracked with tracking number {tracking_no}.")
        return jsonify({'status': 'success', 'shipment_data': shipment_data}), 200
    except sqlite3.Error as e:
        logging.error(f"SQL error: {e}")
        return jsonify({'status': 'error', 'message': 'Database error occurred.'}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred.'}), 500
    finally:
        if db:
            db.close()


if __name__ == '__main__':
    app.run(port=5002, debug=True)
