from allauth.account.adapter import DefaultAccountAdapter
from django import forms

import re


class AccountAdapter(DefaultAccountAdapter):
    email_matcher = re.compile(r'^oopsdude(?:\+\w+)?@gmail\.com$')

    def is_open_for_signup(self, request):
        if request.method == 'GET':
            return super().is_open_for_signup(request)
        else:
            email = request.POST['email']
            if self.email_matcher.match(email):
                return super().is_open_for_signup(request)
            else:
                return False