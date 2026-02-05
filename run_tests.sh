

echo "🧪 Uruchamianie testów PhoneLink..."
echo ""


python -m pytest tests/ -v --tb=short --cov=Core --cov-report=html

echo ""
echo "✅ Raporty dostępne w htmlcov/index.html"
