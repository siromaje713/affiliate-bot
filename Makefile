.PHONY: install post dry analytics research buzz cron-setup cron-remove cron-list

install:
	pip3 install -r requirements.txt

post:
	python3 orchestrator.py --mode post

dry:
	python3 orchestrator.py --mode post --dry-run

analytics:
	python3 orchestrator.py --mode analytics

research:
	python3 -c "from agents import researcher; import json; print(json.dumps(researcher.run(), ensure_ascii=False, indent=2))"

buzz:
	python3 -c "from agents import buzz_researcher; import json; print(json.dumps(buzz_researcher.run(), ensure_ascii=False, indent=2))"

cron-setup:
	@echo "スケジュール登録中: 毎日6時・12時・21時"
	(crontab -l 2>/dev/null | grep -v 'affiliate-bot'; \
	 echo "0 6  * * * cd $(PWD) && make post >> /tmp/affiliate-bot.log 2>&1"; \
	 echo "0 12 * * * cd $(PWD) && make post >> /tmp/affiliate-bot.log 2>&1"; \
	 echo "0 21 * * * cd $(PWD) && make post >> /tmp/affiliate-bot.log 2>&1") | crontab -
	@echo "登録完了:"
	@crontab -l | grep affiliate-bot

cron-remove:
	@echo "スケジュール削除中..."
	crontab -l 2>/dev/null | grep -v 'affiliate-bot' | crontab -
	@echo "削除完了"

cron-list:
	@crontab -l 2>/dev/null | grep affiliate-bot || echo "登録なし"
