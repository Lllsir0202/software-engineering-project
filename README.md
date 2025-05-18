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
```

### In conda environment
```bash
    conda create -n your_env python=3.7
    conda activate your_env
    conda install flask
    pip install flask-mail
    pip install flask-cors
    conda install email-validator
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