class CustomError(Exception):
    pass


class ConditionCheckFailedError(CustomError):
    pass


# Define integrity exception
class IntegrityError(CustomError):
    pass
