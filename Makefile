help:
	@echo ""
	@echo "usage: make COMMAND"
	@echo ""
	@echo "Commands:"
	@echo ""
	@echo "    s      Run the scraper (sends to \$$WEBHOOK_URL)"
	@echo "    dry    Preview payloads without sending (DRY_RUN=1)"
	@echo ""

s:
	@python3 main.py

dry:
	@DRY_RUN=1 python3 main.py

.PHONY: s dry help
