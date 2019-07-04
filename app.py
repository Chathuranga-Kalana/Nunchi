import os

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import flask_excel as excel
import flask_csv as flaskcsv
import json


from flask import Flask,render_template, redirect, url_for, request, session, flash, make_response,send_file,send_from_directory
from jinja2 import  Environment,FileSystemLoader
from flask_wkhtmltopdf import Wkhtmltopdf
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash




from flask_weasyprint import HTML, render_pdf
from datetime import date

from sklearn.externals import joblib

from sklearn.naive_bayes import GaussianNB



absenteeism_data = pd.read_excel('dataset/Absenteeism_at_work.xls')

UPLOAD_FOLDER = 'E:/final year/FYP/project/dataset'
UPLOADED_ITEMS_DEST = 'C:/Users/DELL/Downloads'
ALLOWED_EXTENSION = set(['csv'])


app = Flask(__name__)
app.secret_key = 'vjadvfoshfsdfoj'

app.config['UPLOADED_ITEMS_DEST'] =UPLOADED_ITEMS_DEST
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MYSQL_HOST'] = 'localhost'
app.config["MYSQL_USER"] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'fyp'


# path_wkthmltopdf = r'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'
#
# config = pdfkit.configuration(wkhtmltopdf=path_wkthmltopdf)

mysql = MySQL(app)



def allowed_file(filename):
    return  '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSION


#register person
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        userName =  request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO admin(username, password, email) VALUES(%s ,%s, %s)',(userName, password, email))
        mysql.connection.commit()
        cursor.close()
        session['logged_in'] = True
        return redirect(url_for('dash'))


    return render_template('register.html')


# #pdf create
@app.route('/report',methods=['GET','POST'])
def report():
    count1 = absenteeism_data['ID'].unique()
    absenteeism_data['Work load Average/day '] = absenteeism_data['Work load Average/day '].astype(str).str.replace(',',
                                                                                                                    '')
    workload_sum = round((absenteeism_data['Work load Average/day '].astype(float).sum()) / 36)
    today = date.today()
    today = today.isoformat()

    eID = absenteeism_data.groupby('ID').size().sort_values(ascending=True).index[-1]

    count = {'count': count1.size,
              'work_load': workload_sum,
             'dategraph': today,
             'eID': eID
             }

    environment = Environment(loader=FileSystemLoader('templates'))
    template =  environment.get_template("report.html")
    html = template.render(count)
    HTML(string=html).write_pdf(today+'.pdf')
    return  send_file(today+".pdf",cache_timeout=0)

    # html = render_template('index.html',  count = count)
    # HTML(string=html).write_pdf("report.pdf")
    # return render_pdf(HTML(string=html))





# login page
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':

        userName = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT COUNT(1) FROM admin WHERE username = (%s)',[userName])
        if cursor.fetchone()[0]:
            cursor.execute('SELECT password FROM admin WHERE username = (%s)',[userName])
            for row in cursor.fetchall():
                hPassword = row[0]
                # passw =  generate_password_hash(password)
                if check_password_hash(hPassword, password):
                    session['logged_in'] = True
                    return redirect(url_for('dash'))
                else:
                    error = 'Invalid Credentials. Please try again.'
        else:
            error = 'Invalid Credentials. Please try again.'
        cursor.close()
    return render_template('login.html', error = error)

#admin dashboard
@app.route('/dash')
def dash():
    if session['logged_in']:
        #get uique ids of employee
        count1= absenteeism_data['ID'].unique()
        absenteeism_data['Work load Average/day '] = absenteeism_data['Work load Average/day '].astype(str).str.replace(',', '')
        workload_sum = round((absenteeism_data['Work load Average/day '].astype(float).sum())/36)

        #find most absented employee
        eID = absenteeism_data.groupby('ID').size().sort_values(ascending=True).index[-1]
        print(eID)


        #check whether today folder available
        today = date.today()
        today = today.isoformat()

        if os.path.exists("E:/final year/FYP/project/static/images/overall/" + today):
            count = [{'count': count1.size,
                      'work_load': workload_sum,
                      'dategraph': today,
                      'eID': eID}
                     ]
            return render_template('index.html', count = count)
        else:
            os.mkdir("E:/final year/FYP/project/static/images/overall/" + today + "/")
            #select needed columns to generate the graphs
            categories = ['Reason for absence', 'Month of absence', 'Day of the week', 'Seasons',
                          'Disciplinary failure', 'Education', 'Son','Social drinker', 'Social smoker']
            #create graphs
            for col in categories:
                sns.catplot(data=absenteeism_data, x=col, kind='count', height=4, aspect=2)
                plt.savefig("E:/final year/FYP/project/static/images/overall/"+today+"/"+col+".png")


            count = [{'count': count1.size,
                      'work_load': workload_sum,
                      'dategraph': today}
                     ]
            return render_template('index.html', count = count)
    else:
        return render_template('login.html')


# csv file upload
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    error = None
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(url_for('dash'))

        file = request.files['file']
        if file.filename == '':
            flash('No file selected for uploading')
            return redirect(url_for('dash'))

        if file and allowed_file(file.filename):
            flash('File upload Successfully ')
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('dash'))
        else:
            flash('File Does not support')
            return redirect(url_for('dash'))


#prediction using form

@app.route('/prediction', methods=['GET', 'POST'])
def prediction():
    if request.method == 'POST':

        eID = request.form['eID']
        workload = request.form['workload']

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM employee WHERE id =(%s)',[eID])
        mysql.connection.commit()
        for row in cursor.fetchall():
            transp = row[1]
            son = row[2]
            age = row[3]
            servtime = row[4]
            pet = row[5]
            height = row[6]



        cursor.close()

        headers = ["Transportation expense", "Son", "Age", "Service time", "Pet", "Height",
                       "Work load Average/day "]
        input_variables = pd.DataFrame([[transp, son, age, servtime, pet, height, workload]],
                                           columns=headers,
                                           dtype=float,
                                           index=['input'])


        loaded_model = joblib.load("model/xg_model.pkl")
        prediction = loaded_model.predict(input_variables)
        data = [{'eID': eID,
                 'prediction':prediction}]
        print(prediction)
        return render_template("prediction.html", prediction=data)
    else:
        return render_template("prediction.html")

# show user progress using user id
@app.route('/userinfo', methods=('GET', 'POST'))
def user_info():
    sort_id = absenteeism_data.sort_values(by=['ID'])
    unique_id = sort_id['ID'].unique().tolist()
    return render_template('employees.html', unique_id=unique_id)



# employee data
@app.route('/employee', methods=('GET', 'POST'))
def employee():
    id = request.args['id']

    if os.path.exists("E:/final year/FYP/project/static/images/model/"+id):
        return render_template("employee.html", id=id)
    else:
        os.mkdir("E:/final year/FYP/project/static/images/model/" + id +"/")
        is_id_df = absenteeism_data['ID'] == int(id)
        id_df = absenteeism_data[is_id_df]
        sns.catplot(data=id_df, x="Reason for absence", kind='count', height=4, aspect=2)
        plt.savefig("E:/final year/FYP/project/static/images/model/" + id + "/reasons" + ".png")
        sns.catplot(data=id_df, x="Day of the week", kind='count', height=4, aspect=2)
        plt.savefig("E:/final year/FYP/project/static/images/model/" + id + "/day" + ".png")
        sns.catplot(data=id_df, x="Month of absence", kind='count', height=4, aspect=2)
        plt.savefig("E:/final year/FYP/project/static/images/model/" + id + "/month" + ".png")
        return render_template("employee.html", id=id)




# logout
@app.route('/logout')
def logout():
    session['logged_in'] = False
    return redirect(url_for('login'))



# erorr handeling for web app
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500



if __name__ =="__main__":
    app.run(debug=True)

