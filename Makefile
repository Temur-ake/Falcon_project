mig:
	python3 manage.py makemigrations
	python3 manage.py migrate
app:
	python manage.py startapp misol

run:
	python3 manage.py runserver
sup:
	python3 manage.py createsuperuser

celery:
	celery -A root worker -l INFO

beat:
	celery -A root  beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler

dump:
	python3 manage.py dumpdata --indent=2 apps.Category > categories.json


load:
	python3 manage.py loaddata products