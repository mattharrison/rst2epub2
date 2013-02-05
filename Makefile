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

.PHONY: develop
develop: deps
	$(PY) setup.py develop

# rm_env isn't a file so it needs to be marked as "phony"
.PHONY: rm_env
rm_env:
	rm -rf env

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
build:
	$(PY) setup.py sdist

.PHONY: upload
upload:
	$(PY) setup.py sdist upload
