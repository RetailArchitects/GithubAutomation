from flask_wtf import Form
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, NumberRange

class ReleaseConfigForm(Form):
  name = StringField('name', validators=[DataRequired()])
  sp_target = IntegerField('sp_target', validators=[DataRequired(), NumberRange(min=1)])
