# Software-Engineering-project
This is NKU software engineering project

## Basic Environment
    platform = ubuntu 24.04
    python = 3.7.16
    This project requires the following Python packages:
    - flask 
    - flask-mail
    - flask-cors
    - email-validator
  
    (Attention:Following two packages CANNOT use conda to install,please use bash given by our README.md)

## Quick Setup

### common(Not use conda)
please ensure you have __install python and version=3.7 is recommended__

```bash
    pip install flask
    pip install flask-mail
    pip install flask-cors
    pip install email-validator
    pip install flask_sqlalchemy
    pip install pymysql
    pip install flask_migrate
    ...
```

### In conda environment
```bash
    conda create -n your_env python=3.7
    conda activate your_env
    conda install flask
    pip install flask-mail
    pip install flask-cors
    conda install email-validator
    pip install flask_sqlalchemy
    pip install pymysql
    pip install flask_migrate
    ...
```
Attention: **you can REPLACE __your_env__ by any name you like.**

### Setup by init.sh
We also give a init.sh to help you set up environment required quickly. However it requires you platform is **linux**

```bash
    chmod +x init.sh
    ./init.sh
```
If you'd like to setup it in conda environment, please input 1.Also,you can replace ```myenv``` in the following line of init.sh ```ENV_NAME="myenv"``` by any name you like.

## Quick run
We give a **Makefile** to assist run.

You can run following commands:
    
    run: used to run app.py.
    clean-port: clean in-use port,default clean before run.

## Dataset
We just origanise dataset like following structure:
    
```
    In the workspace
    -data
        -waterquality
            -dir(year-month)
                -detailed data(year-month-day.json)
```

## Set up database
Now we can consider to move all the data into a database, here we name it as ``smart_farm``, you can choose whatever you like but you need to change source code accordingly.

``` bash
    chmod +x install_mysql.sh
    ./install_mysql.sh
```

Then you can initialize the database as following(Platform=Linux)
``` bash
    mysql -u root -p

    ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'yourpassword';

    CREATE DATABASE smart_farm DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;



```
**Attention**:you can replace 'yourpassword' with your own password

To use it in the ``python``, we need to install according packages, following is the commands.

``` bash
    # If you have set up the environment by our ``init.sh``, it has be prepared.
    pip install pymysql
    # Before this , you should create a .env file and add the next code into it.
    DB_URL=mysql+pymysql://root:yourpassword@localhost:3306/smart_farm

    # Then we can run this python code to move our data into database
    python3 import_data.py
```

Here we use ``flask_migrate`` to create a database tables:

``` bash
    flask db init       # Only once
    flask db migrate -m "Initial migration"
    flask db upgrade    # initialize all tablse
```
**Attention**: Must run in the root directory **!!!**

# FAQ
1. ``flask db init`` failed

> mainly because flask is not in the environment of ``conda``, you can check by ``which flask`` to identify which flask you are using. If you are using a ``flask`` which is not in conda env , you can first deactivate and then uninstall it, then activate conda to install again.