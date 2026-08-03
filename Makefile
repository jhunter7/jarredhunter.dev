.PHONY: build preview clean deps

PORT ?= 5500

deps:
	pip3 install -r scripts/requirements.txt

build:
	python3 scripts/build_blog.py

preview: build
	cd src && python3 -m http.server $(PORT)

clean:
	rm -rf src/blog src/sitemap.xml src/robots.txt
