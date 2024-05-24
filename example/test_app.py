import unittest
from app import app  # Make sure this import matches the location and name of your Flask application module

class TestFlaskApp(unittest.TestCase):
    def setUp(self):
        # Configure the app for testing
        app.config['TESTING'] = True
        # Create a test client
        self.client = app.test_client()

    def test_info_endpoint(self):
        # Send a GET request to the '/' endpoint
        response = self.client.get('/')
        # Check that the response is OK
        self.assertEqual(response.status_code, 200)
        # Check the data returned
        self.assertEqual(response.data.decode('utf-8'), "Docker alkalmazás")

    def test_hello_endpoint(self):
        # Send a GET request to the '/' endpoint
        response = self.client.get('/hello')
        # Check that the response is OK
        self.assertEqual(response.status_code, 200)
        # Check the data returned
        self.assertEqual(response.data.decode('utf-8'), "Helló Világ!")

if __name__ == '__main__':
    unittest.main()
