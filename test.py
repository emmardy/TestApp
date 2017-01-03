from flask import Flask 
from app import app
import unittest


class FlaskTestCase(unittest.TestCase):

	 def test_index(self):
	     tester = app.test_client(self)
	     response = tester.get('/login', content_type="html/text")
	     self.assertEqual(response.status_code, 200)


     def test_login_page_loads(self):
     	 tester = app.test_client(self) 
     	 response = tester.get('/login', content-type="html/test")
     	 self.assertTrue(b'Please Login' in response.data)