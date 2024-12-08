from flask import Flask, request, jsonify
import uuid
import logging
import sqlite3

app = Flask(__name__)

# Configuring logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# In-memory store for payment activities
payment_history = []


def get_db():
    conn = sqlite3.connect('penta_book.db')
    conn.row_factory = sqlite3.Row
    return conn


# Retrieving valid payment methods from the database
def get_valid_payment_methods():
    try:
        db = get_db()
        cur = db.execute('SELECT method_id, method_name FROM paymentmethods')
        payment_methods = cur.fetchall()
        return {str(method['method_id']): method['method_name'] for method in payment_methods}
    except Exception as e:
        logger.error(f"Error retrieving payment methods from database: {e}")
        return {}


@app.route('/process_payment', methods=['POST'])
def process_payment():
    data = request.json
    app.logger.debug(f"Received payment request: {data}")

    if not data.get('amount') or not isinstance(data['amount'], (int, float)):
        app.logger.debug('Validation Error: Missing or invalid amount')
        return jsonify({'status': 'failed', 'message': 'Missing or invalid amount'}), 400
    if not data.get('method_id'):
        app.logger.debug('Validation Error: Missing method_id')
        return jsonify({'status': 'failed', 'message': 'Missing method_id'}), 400
    if not data.get('method_name'):
        app.logger.debug('Validation Error: Missing method_name')
        return jsonify({'status': 'failed', 'message': 'Missing method_name'}), 400
    if not data.get('order_id'):
        app.logger.debug('Validation Error: Missing order_id')
        return jsonify({'status': 'failed', 'message': 'Missing order_id'}), 400

    # Fetch valid payment methods from the database
    valid_payment_methods = get_valid_payment_methods()
    method_id = str(data['method_id'])
    app.logger.debug(f"Validating method_id: {method_id} and method_name: {data['method_name']}")

    if method_id not in valid_payment_methods or valid_payment_methods[method_id] != data['method_name']:
        app.logger.debug(f"Validation Error: Invalid method_id ({method_id}) or method_name ({data['method_name']})")
        return jsonify({'status': 'failed', 'message': 'Invalid method_id or method_name'}), 400

    # Simulate transaction processing
    transaction_id = str(uuid.uuid4())
    payment_status = 'approved'  # Setting all payments to approved
    app.logger.debug(f"Transaction ID: {transaction_id}, Payment Status: {payment_status}")

    response = {
        'transaction_id': transaction_id,
        'payment_status': payment_status,
        'method_id': method_id,
        'method_name': data['method_name'],
        'order_id': data['order_id']
    }

    app.logger.info(f'Processed payment: {response}')

    return jsonify({'status': 'success', 'data': response}), 200


@app.route('/payment_history', methods=['GET'])
def get_payment_history():
    return jsonify({'status': 'success', 'data': payment_history}), 200


if __name__ == '__main__':
    app.run(port=5001, debug=True)
