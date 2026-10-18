# Cretan Staffing Demo

A demo Django staffing portal with sample jobs, candidate applications, and a staff dashboard. This demo is not production-ready and should not be used for real candidate data.

## Local run

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Demo admin requires creating a user with `python manage.py createsuperuser`.
