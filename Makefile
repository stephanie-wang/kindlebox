.PHONY: pull

pull:
	git pull
	pip install -r requirements.txt
	./run.py db upgrade
