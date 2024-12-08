from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FloatField, IntegerField, SelectField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from flask_wtf.file import FileAllowed



class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm = PasswordField('Confirm Password',
                            validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    dob = StringField('Date of Birth', validators=[DataRequired()])
    phone_number = StringField('Phone Number', validators=[DataRequired()])
    buyer_address = StringField('Address', validators=[DataRequired()])
    submit = SubmitField('Register')


class ShopRegisterForm(FlaskForm):
    shop_name = StringField('Shop Name', validators=[DataRequired(), Length(min=2, max=20)])
    owner_name = StringField('Owner Name', validators=[DataRequired(), Length(min=2, max=20)])
    shop_phone = StringField('Shop Phone', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    shop_address = StringField('Shop Address', validators=[DataRequired()])
    shop_email = StringField('Email', validators=[DataRequired(), Email()])
    shop_description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Register as Shop')

class ShopLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class BookForm(FlaskForm):
    book_name = StringField('Book Name', validators=[DataRequired()])
    isbn = StringField('ISBN', validators=[DataRequired()])
    author = StringField('Author', validators=[DataRequired()])
    desc = TextAreaField('Description', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    stock = IntegerField('Stock', validators=[DataRequired(), NumberRange(min=0)])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    image = FileField('Book Cover Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    submit = SubmitField('Save')

class ShopUpdateForm(FlaskForm):
    shop_name = StringField('Shop Name', validators=[DataRequired()])
    owner_name = StringField('Owner Name', validators=[DataRequired()])
    shop_phone = StringField('Phone Number', validators=[DataRequired()])
    shop_address = StringField('Address', validators=[DataRequired()])
    shop_email = StringField('Email', validators=[DataRequired(), Email()])
    shop_description = StringField('Description')
    submit = SubmitField('Update')

