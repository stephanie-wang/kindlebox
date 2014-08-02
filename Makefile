.PHONY: pull, heroku

default:
	./run.py runserver

pull:
	git pull
	@echo "\nInstalling virtualenv requirements...";
	pip install -r requirements.txt
	@echo "\nRunning any migrations..."
	./run.py db upgrade

heroku:
	@echo "Starting push to Heroku..."
	git push heroku master
	@echo "\nRunning any migrations..."
	heroku run 'python run.py db upgrade'
