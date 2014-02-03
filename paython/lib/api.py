from __future__ import absolute_import, unicode_literals

import httplib
import urllib
import xml.dom.minidom

from .utils import parse_xml
from ..gateways.core import Gateway
from ..exceptions import RequestError, GatewayError, DataValidationError


class XMLGateway(Gateway):
    def __init__(self, host, translations, debug=False, special_params={}, headers={}):
        """ initalize API call session

        host: hostname (apigateway.tld)
        auth: accept a tuple with (username,password)
        debug: True/False
        """
        self.doc = xml.dom.minidom.Document()
        self.api_host = host
        self.debug = debug
        self.parse_xml = parse_xml
        self.special_ssl = special_params
        self.headers = headers
        super(XMLGateway, self).__init__(translations=translations, debug=debug)

    @property
    def envelope(self):
        """
        This method should return the document or element which set() will use to add new elements into.
        Could be used to envelope XML (as in SOAP requests)
        """
        if hasattr(self, '_envelope'):
            return self._envelope
        self._envelope = self.doc
        return self._envelope

    def set(self, path, child=False, attribute=False):
        """ Accepts a forward slash separated path of XML elements to traverse and create if non existent.
        Optional child and target node attributes can be set. If the `child` attribute is a tuple
        it will create X child nodes by reading each tuple as (name, text, 'attribute:value') where value
        and attributes are optional for each tuple.

        - path: forward slash separated API element path as string (example: "Order/Authentication/Username")
        - child: tuple of child node data or string to create a text node
        - attribute: sets the target XML attributes (string format: "Key:Value")
        """
        try:
            xml_path = path.split('/')
        except AttributeError:
            return  # because if it's None, then don't worry

        envelope = self.envelope

        # traverse full XML element path string `path`
        for element_name in xml_path:
            # get existing XML element by `element_name`
            element = envelope.getElementsByTagName(element_name)
            if element:
                element = element[0]

            # create element if non existing or target element
            if not element or element_name == xml_path[-1:][0]:
                element = self.doc.createElement(element_name)
                envelope.appendChild(element)

            envelope = element

        if child:
            # create child elements from an tuple with optional text node or attributes
            # format: ((name1, text, 'attribute:value'), (name2, text2))
            if isinstance(child, tuple):
                for obj in child:
                    child = self.doc.createElement(obj[0])
                    if len(obj) >= 2:
                        element = self.doc.createTextNode(str(obj[1]))
                        child.appendChild(element)
                    if len(obj) == 3:
                        a = obj[2].split(':')
                        child.setAttribute(a[0], a[1])
                    envelope.appendChild(child)
            # create a single text child node
            else:
                element = self.doc.createTextNode(str(child))
                envelope.appendChild(element)

        # target element attributes
        if attribute:
            #checking to see if we have a list of attributes
            if '|' in attribute:
                attributes = attribute.split('|')
            else:
                #if not just put this into a list so we have the same data type no matter what
                attributes = [attribute]

            # adding attributes for each item
            for attribute in attributes:
                attribute = attribute.split(':')
                envelope.setAttribute(attribute[0], attribute[1])

    def request_xml(self):
        """
        Stringifies request xml for debugging
        """
        return self.doc.toprettyxml()

    def make_request(self, api_uri):
        """
        Submits the API request as XML formated string via HTTP POST and parse gateway response.
        This needs to be run after adding some data via 'set'
        """
        request_body = self.doc.toxml('utf-8')

        api = httplib.HTTPSConnection(self.api_host, **self.special_ssl)

        api.connect()
        headers = {
            'Host': self.api_host,
            'Content-type': 'text/xml; charset="utf-8"',
            'Content-length': str(len(request_body)),
            'User-Agent': 'yourdomain.net',
        }
        headers.update(self.headers)
        for header, value in headers.items():
            api.putheader(header, value)
        api.endheaders()
        api.send(request_body)

        resp = api.getresponse()
        resp_data = resp.read()

        # parse API call response
        if not resp.status == 200:
            raise RequestError("Gateway returned %i status" % resp.status)

        # parse XML response and return as dict
        try:
            resp_dict = self.parse_xml(resp_data)
        except:
            try:
                resp_dict = self.parse_xml('<?xml version="1.0"?><response>%s</response>' % resp_data)
            except:
                raise RequestError("Could not parse XML into JSON")

        return resp_dict


class SOAPGateway(XMLGateway):
    pass


class GetGateway(Gateway):
    REQUEST_DICT = {}
    debug = False

    def __init__(self, translations, debug):
        """core GETgateway class"""
        super(GetGateway, self).__init__(translations=translations, debug=debug)
        self.debug = debug

    def set(self, key, value):
        """
        Setups request dict for Get
        """
        self.REQUEST_DICT[key] = value

    def unset(self, key):
        """
        Sets up request dict for Get
        """
        try:
            del self.REQUEST_DICT[key]
        except KeyError:
            raise DataValidationError("The key being unset is non-existent in the request dictionary.")

    def query_string(self):
        """
        Build the query string to use later (in get)
        """
        request_query = '?%s' % urllib.urlencode(self.REQUEST_DICT)
        return request_query

    def make_request(self, uri):
        """
        GETs url with params - simple enough... string uri, string params
        """
        try:
            params = self.query_string()
            request = urllib.urlopen('%s%s' % (uri, params))

            return request.read()
        except:
            raise GatewayError("Error making request to gateway")


class PostGateway(Gateway):
    REQUEST_DICT = {}
    debug = False

    def __init__(self, translations, debug):
        """
        core POST gateway class
        """
        super(PostGateway, self).__init__(translations=translations, debug=debug)
        self.debug = debug

    def set(self, key, value):
        """
        Setups request dict for Post
        """
        self.REQUEST_DICT[key] = value

    def params(self):
        """
        returns arguments that are going to be sent to the POST (here for debugging)
        """
        return urllib.urlencode(self.REQUEST_DICT)

    def make_request(self, uri):
        """
        POSTs to url with params (self.REQUEST_DICT) - simple enough... string uri, dict params
        """
        try:
            request = urllib.urlopen(uri, self.params())
            return request.read()
        except:
            raise GatewayError("Error making request to gateway")
