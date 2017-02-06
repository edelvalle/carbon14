
class Carbon14Error(Exception):
    pass


class TokenizerError(Carbon14Error):

    def __init__(self, value, line, column):
        self.value = value
        self.line = line
        self.column = column
        super().__init__('Syntax error: "%s" unexpected at %d:%d' % (
            value, line, column
        ))


class LexicalError(Carbon14Error):

    def __init__(self, value=None, line=1, column=1, expected_kinds=None):
        self.value = value
        self.line = line
        self.column = column
        self.expected_kinds = expected_kinds

        if expected_kinds is None:
            msg = 'Unexpected EOF while parsing %s at %d:%d' % (
                value, line, column
            )
        else:
            msg = 'Unexpected "%s" expecting %s at %d:%d' % (
                value, ', '.join(expected_kinds), line, column
            )
        super().__init__(msg)


class MissingCollection(Carbon14Error):

    def __init__(self, collection_name):
        msg = 'Attempt to query non-existing collection "%s".' % collection_name
        super().__init__(msg)
