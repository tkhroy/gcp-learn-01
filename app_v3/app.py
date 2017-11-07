#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, redirect, url_for
from flask import escape, Markup
from flask import send_from_directory

from wtforms import Form, TextAreaField, StringField, validators, ValidationError
import arrow

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

from flask_wtf.file import FileField
from werkzeug.utils import secure_filename
from werkzeug.datastructures import CombinedMultiDict
from gcloud import storage
import uuid, tempfile

import os
import pdb

Debug = os.path.exists("/home/itmember")

#### Edit Here
dbuser = 'appuser'
dbpass = '1qaz6yhn'
project_id = 'project-ml-rel'

upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)),'uploads')

if Debug == True :
    dburi = 'mysql+pymysql://%s:%s@localhost/message_db' % (dbuser, dbpass)
    storage_path = 'uploads'
    print(upload_folder)
else:
    dbinstance = 'project-ml-rel:asia-northeast1:websql'
    dburi = 'mysql+pymysql://%s:%s@/message_db?unix_socket=/cloudsql/%s' % (dbuser, dbpass, dbinstance)
    bucket_name = '%s-storage' % project_id
    bucket = storage.Client().get_bucket(bucket_name)
    storage_path = 'https://storage.cloud.google.com/%s' % bucket_name

####

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = dburi
db = SQLAlchemy(app)
app.config['UPLOAD_FOLDER'] = upload_folder

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.String(19))
    name = db.Column(db.String(16))
    message = db.Column(db.String(1024))
    filename = db.Column(db.String(128))

    def __init__(self, timestamp, name, message, filename):
        self.timestamp = timestamp
        self.name = name
        self.message = message
        self.filename = filename

db.create_all()

@app.template_filter('add_br')
def linesep_to_br_filter(s):
    return escape(s).replace('\n', Markup('<br>'))

def is_image():
    def _is_image(form, field):
        extensions = ['jpg', 'jpeg', 'png', 'gif']
        if field.data and \
           field.data.filename.split('.')[-1] not in extensions:
            raise ValidationError()
    return _is_image

class MessageForm(Form):
    input_name = StringField(u'お名前', [validators.Length(min=1, max=16)])
    input_message = TextAreaField(u'メッセージ',
                                  [validators.Length(min=1, max=1024)])
    input_photo = FileField(u'画像添付(jpg, jpeg, png, gif)',
                            validators=[is_image()])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/messages')
def messages():
    form = MessageForm(request.form)
    last_messages = Message.query.order_by(desc(Message.id)).limit(5)
    last_messages = [message for message in last_messages]
    last_messages.reverse()
    return render_template('messages.html', storage_path=storage_path,
                           form=form, messages=last_messages)

@app.route('/post', methods=['POST'])
def post():
    form = MessageForm(CombinedMultiDict((request.files, request.form)))
    if request.method == 'POST' and form.validate():
        timestamp = arrow.utcnow().to('Asia/Tokyo').format('YYYY/MM/DD HH:mm:ss')
        name = request.form['input_name']
        message = request.form['input_message']
        if form.input_photo.data.filename:
            filename = str(uuid.uuid4()) + \
                       secure_filename(form.input_photo.data.filename)
            uploadfile = os.path.join(app.config['UPLOAD_FOLDER'],filename)
            form.input_photo.data.save(uploadfile)

            if Debug == True:
                pass
            else:
                blob2 = bucket.blob(filename)
                blob2.upload_from_filename(filename=uploadfile)

            db.session.add(Message(timestamp, name, message, filename))
            db.session.commit()
        else:
            db.session.add(Message(timestamp, name, message, filename=None))
            db.session.commit()
        return render_template('post.html', name=name, timestamp=timestamp)
    else:
        return redirect(url_for('messages'))
  
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80, debug=Debug)
