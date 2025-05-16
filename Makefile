include env.mk

PYTHON ?= conda run -n $(ENV_NAME) python

ifeq ($(USE_CONDA),1)
PYTHON := conda run -n $(ENV_NAME) python
else
PYTHON := $(PYTHON_BIN)
endif

run:clean-port
	@echo "Starting Flask server..."
	@echo "Flask server started."
	@echo "Access the server at http://localhost:5000"
	@echo "Press Ctrl+C to stop the server."
	@eval $(PYTHON) app.py

clean-port:
	@PORT=5000; PID=$$(lsof -ti tcp:$$PORT); \
	if [ -n "$$PID" ]; then \
		echo "Killing process $$PID on port $$PORT..."; \
		kill -9 $$PID; \
	else \
		echo "No process on port $$PORT"; \
	fi

