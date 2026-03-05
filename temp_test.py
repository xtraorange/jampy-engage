from src.ui import create_app
app = create_app()
app.testing = True
client = app.test_client()
rv = client.get('/api/pick-folder')
print(rv.status_code, rv.get_data())
