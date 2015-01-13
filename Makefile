.PHONY: pull, heroku

default:
	DEBUG=1
	-sudo rabbitmq-server --detached
	python run.py runserver

pull:
	git pull
	@echo "\nInstalling virtualenv requirements...";
	pip install -r requirements.txt
	jsx app/static/js/src app/static/js/build
	@echo "\nRunning any migrations..."
	./run.py db upgrade
	sudo service uwsgi restart
	sudo service celeryd restart

heroku:
	@echo "Starting push to Heroku..."
	git push heroku master
	@echo "\nRunning any migrations..."
	heroku run 'python run.py db upgrade'
