push:
python3 -m py_compile orchestrator.py && echo "✅ syntax OK" && git add -A && git commit -m "$(msg)" && git push origin main
