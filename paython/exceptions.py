class DataValidationError(Exception):
    """ Errors when data is corrupt, malformed or just plain wrong """
    pass


class MissingDataError(Exception):
    """ Errors when data is missing in developer API call """
    pass


class GatewayError(Exception):
    """ Errors returned from API Gateway """
    pass


class RequestError(Exception):
    """ Errors during the API Request """
    pass


class MissingTranslationError(Exception):
    """ Errors with trying to find a translation"""
    pass
