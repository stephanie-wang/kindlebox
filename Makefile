.PHONY: pull, heroku

default:
	DEBUG=1
	-sudo rabbitmq-server --detached
	~/redis-2.8.12/src/redis-server &
	python run.py runserver

pull:
	git pull
	@echo "\nInstalling virtualenv requirements...";
	pip install -r requirements.txt
	jsx app/static/js/src app/static/js/build

	sudo service celeryd stop
	# Clean up any temporary files from the celery workers
	sudo rm -r /tmp/kindlebox/*
	@echo "\nRunning any migrations..."
	./run.py db upgrade
	sudo service celeryd start

	sudo service uwsgi restart

heroku:
	@echo "Starting push to Heroku..."
	git push heroku master
	@echo "\nRunning any migrations..."
	heroku run 'python run.py db upgrade'
