from __future__ import absolute_import, unicode_literals

import time
import urlparse
import logging

from ..exceptions import MissingDataError
from ..lib.api import PostGateway

logger = logging.getLogger(__name__)


class InnovativeGW(PostGateway):
    """TODO needs docstring"""
    VERSION = 'WebCharge_v5.06'

    # This is how we determine whether or not we allow 'test' as an init param
    API_URI = {
        'live': 'https://transactions.innovativegateway.com/servlet/com.gateway.aai.Aai'
    }

    # This is how we translate the common Paython fields to Gateway specific fields
    # it goes like this: 'paython_key' ==> 'gateway_specific_parameter'
    REQUEST_FIELDS = {
        #contact
        'full_name': 'ccname',
        'first_name': None,
        'last_name': None,
        'email': 'email',
        'phone': 'bphone',
        #billing
        'address': 'baddress',
        'address2': 'baddress1',
        'city': 'bcity',
        'state': 'bstate',
        'zipcode': 'bzip',
        'country': 'bcountry',
        'ip': None,
        #card
        'number': 'ccnumber',
        'exp_date': None,
        'exp_month': 'month',
        'exp_year': 'year',
        'verification_value': 'ccidentifier1',
        'card_type': 'cardtype',
        #shipping
        'ship_full_name': None,
        'ship_first_name': None,
        'ship_last_name': None,
        'ship_to_co': None,
        'ship_address': 'saddress1',
        'ship_address2': 'saddress',
        'ship_city': 'scity',
        'ship_state': 'sstate',
        'ship_zipcode': 'szip',
        'ship_country': 'scountry',
        #transation
        'amount': 'fulltotal',
        'trans_type': 'trantype',
        'trans_id': 'trans_id',
        'alt_trans_id': 'reference',
    }

    # Response Code: 1 = Approved, 2 = Declined, 3 = Error, 4 = Held for Review
    # AVS Responses: A = Address (Street) matches, ZIP does not,  P = AVS not applicable for this transaction,
    # AVS Responses (cont'd): W = Nine digit ZIP matches, Address (Street) does not, X = Address (Street) and nine digit ZIP match,
    # AVS Responses (cont'd): Y = Address (Street) and five digit ZIP match, Z = Five digit ZIP matches, Address (Street) does not
    # AVS Responses (cont'd): N = Neither the street address nor the postal code matches. R = Retry, System unavailable (maybe due to timeout)
    # AVS Responses (cont'd): S = Service not supported. U = Address information unavailable. E = Data not available/error invalid.
    # AVS Responses (cont'd): G = Non-US card issuer that does not participate in AVS
    # response index keys to map the value to its proper dictionary key
    # it goes like this: 'gateway_specific_parameter' ==> 'paython_key'
    RESPONSE_KEYS = {
        'error': 'response_text',
        'messageid': 'auth_code',
        'avs': 'avs_response',
        'anatransid': 'trans_id',
        'fulltotal': 'amount',
        'trantype': 'trans_type',
        'approval': 'alt_trans_id',  # aka "reference" in intuit land
        'ordernumber': 'alt_trans_id2',
        'fulltotal': 'amount',
        #'38':'cvv_response', <-- way of finding out if verification_value is invalid
        #'2':'response_reason_code', <-- mostly for reporting
        #'0':'response_code', <-- mostly for reporting
    }

    debug = False
    test = False

    def __init__(self, username='gatewaytest', password='GateTest2002', debug=False, test=False):
        """
        setting up object so we can run 3 different ways (live, debug, live+debug no test endpoint available)
        """
        self.set('username', username)
        self.set('pw', password)

        # passing fields to bubble up to Base Class
        super(InnovativeGW, self).__init__(translations=self.REQUEST_FIELDS, debug=debug)

        if test:
            self.test = True
            debug_string = " %s.%s.__init__() -- You're in test mode (& debug, obviously) " % (__name__, 'InnovativeGW')
            logger.debug(debug_string.center(80, '='))

    def charge_setup(self):
        """
        standard setup, used for charges
        """
        self.set('target_app', self.VERSION)
        self.set('response_mode', 'simple')
        self.set('response_fmt', 'url_encoded')
        self.set('upg_auth', 'zxcvlkjh')

        debug_string = " %s.%s.charge_setup() Just set up for a charge " % (__name__, 'InnovativeGW')
        logger.debug(debug_string.center(80, '='))

    def auth(self, amount, credit_card=None, billing_info=None, shipping_info=None):
        """
        Sends charge for authorization based on amount
        """
        #set up transaction
        self.charge_setup()  # considering turning this into a decorator?

        #setting transaction data
        self.set(self.REQUEST_FIELDS['amount'], amount)
        self.set(self.REQUEST_FIELDS['trans_type'], 'preauth')

        # validating or building up request
        if not credit_card:
            logger.debug("%s.%s.auth()  -- No CreditCard object present. You passed in %s " % (__name__, 'InnovativeGW', credit_card))

            raise MissingDataError("You did not pass a CreditCard object into the auth method")
        else:
            self.use_credit_card(credit_card)

        if billing_info:
            self.set_billing_info(**billing_info)

        if shipping_info:
            self.set_shipping_info(**shipping_info)

        # send transaction to gateway!
        response, response_time = self.request()
        return self.parse(response, response_time)

    def settle(self, amount, trans_id, ref):
        """
        Sends prior authorization to be settled based on amount & trans_id PRIOR_AUTH_CAPTURE
        """
        #set up transaction
        self.charge_setup()  # considering turning this into a decorator?

        #setting transaction data
        self.set(self.REQUEST_FIELDS['trans_type'], 'postauth')
        self.set(self.REQUEST_FIELDS['amount'], amount)
        self.set(self.REQUEST_FIELDS['trans_id'], trans_id)
        self.set(self.REQUEST_FIELDS['alt_trans_id'], ref)
        self.set('authamount', amount)  # hardcoded because of uniqueness to gateway

        # send transaction to gateway!
        response, response_time = self.request()
        return self.parse(response, response_time)

    def capture(self, amount, credit_card=None, billing_info=None, shipping_info=None):
        """
        Sends transaction for capture (same day settlement) based on amount.
        """
        #set up transaction
        self.charge_setup()  # considering turning this into a decorator?

        #setting transaction data
        self.set(self.REQUEST_FIELDS['amount'], amount)
        self.set(self.REQUEST_FIELDS['trans_type'], 'sale')

        # validating or building up request
        if not credit_card:
            logger.debug("%s.%s.capture()  -- No CreditCard object present. You passed in %s " % (__name__, 'InnovativeGW', credit_card))

            raise MissingDataError("You did not pass a CreditCard object into the auth method")
        else:
            self.use_credit_card(credit_card)

        if billing_info:
            self.set_billing_info(**billing_info)

        if shipping_info:
            self.set_shipping_info(**shipping_info)

        # send transaction to gateway!
        response, response_time = self.request()
        return self.parse(response, response_time)

    def void(self, trans_id, ref, ordernumber):
        """
        Sends a transaction to be voided (in full)
        """
        #set up transaction
        self.charge_setup()  # considering turning this into a decorator?

        #setting transaction data
        self.set(self.REQUEST_FIELDS['trans_type'], 'void')
        self.set(self.REQUEST_FIELDS['trans_id'], trans_id)
        self.set(self.REQUEST_FIELDS['alt_trans_id'], ref)
        self.set('ordernumber', ordernumber)  # hardcoded because of uniqueness to gateway

        # send transaction to gateway!
        response, response_time = self.request()
        return self.parse(response, response_time)

    def credit(self, amount, trans_id, ref, ordernumber):
        """
        Sends a transaction to be refunded (partially or fully)
        """
        #set up transaction
        self.charge_setup()  # considering turning this into a decorator?

        #setting transaction data
        self.set(self.REQUEST_FIELDS['trans_type'], 'credit')
        self.set(self.REQUEST_FIELDS['trans_id'], trans_id)
        self.set(self.REQUEST_FIELDS['alt_trans_id'], ref)
        self.set('ordernumber', ordernumber)  # hardcoded because of uniqueness to gateway

        if amount:  # check to see if we should send an amount
            self.set(self.REQUEST_FIELDS['amount'], amount)

        # send transaction to gateway!
        response, response_time = self.request()
        return self.parse(response, response_time)

    def request(self):
        """
        Makes a request using lib.api.GetGateway.make_request() & move some debugging away from other methods.
        """
        # there is only a live environment, with test credentials
        url = self.API_URI['live']

        debug_string = " %s.%s.request() -- Attempting request to: " % (__name__, 'InnovativeGW')
        logger.debug(debug_string.center(80, '='))
        logger.debug("\n %s with params: %s" %
                     (url, self.params()))

        # make the request
        start = time.time()  # timing it
        response = self.make_request(url)
        end = time.time()  # done timing it
        response_time = '%0.2f' % (end - start)

        debug_string = " %s.%s.request()  -- Request completed in %ss " % (__name__, 'InnovativeGW', response_time)
        logger.debug(debug_string.center(80, '='))

        return response, response_time

    def parse(self, response, response_time):
        """
        On Specific Gateway due differences in response from gateway
        """
        debug_string = " %s.%s.parse() -- Raw response: " % (__name__, 'InnovativeGW')
        logger.debug(debug_string.center(80, '='))
        logger.debug("\n %s" % response)

        new_response = urlparse.parse_qsl(response)
        response = dict(new_response)
        if 'approval' in response:
            approved = True
        else:
            approved = False
            response['approval'] = 'decline'  # there because we have a translation key called "approval" - open to ideas here...

        debug_string = " %s.%s.parse() -- Response as dict: " % (__name__, 'InnovativeGW')
        logger.debug(debug_string.center(80, '='))
        logger.debug('\n%s' % response)

        return self.standardize(response, self.RESPONSE_KEYS, response_time, approved)
