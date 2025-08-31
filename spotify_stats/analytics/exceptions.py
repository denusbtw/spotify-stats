from rest_framework.exceptions import APIException


class InvalidFileContentError(Exception):
    pass


class InvalidRecordError(Exception):
    pass


class SpotifyServiceError(APIException):
    pass
