# variables to use sandboxed binaries
PIP := env/bin/pip
NOSE := env/bin/nosetests
PY := env/bin/python

# -------- Environment --------
# env is a folder so no phony is necessary
env:
	virtualenv env

.PHONY: deps
deps: env
	$(PIP) install -r requirements.txt

# rm_env isn't a file so it needs to be marked as "phony"
.PHONY: rm_env
rm_env:
	rm -rf env


# --------- Dev --------------------
.PHONY: dev
dev: deps
	$(PY) setup.py develop


# --------- Testing ----------
.PHONY: test
test: nose deps
	$(NOSE) test

# nose depends on the nosetests binary
nose: $(NOSE)
$(NOSE): env
	$(PIP) install nose


# --------- PyPi ----------
.PHONY: build
build: env
	$(PY) setup.py sdist

.PHONY: upload
upload: env
	$(PY) setup.py sdist register upload

.PHONY: clean
clean:
	rm -rf dist *.egg-info
