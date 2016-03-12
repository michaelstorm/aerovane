import fileinput
import re
import sys


class Transaction(object):
    def __init__(self, transaction_id, start):
        self.transaction_id = transaction_id
        self.start = start
        self.end = start

    def __repr__(self):
        return "<%s: %s-%s>" % (self.transaction_id, self.start, self.end)


lines = []
transactions = {}
transaction_id = None
line_number = 0

for line in fileinput.input():
    lines.append(line)
    parts = line.split()

    if len(parts) > 3:
        line_id = parts[3]
        line_id_match = re.match(r'\[(\d+)-\d+\]', line_id)

        if line_id_match is not None:
            transaction_id = line_id_match.group(1)

        if transaction_id in transactions:
            transaction = transactions[transaction_id]
            transaction.end = line_number
        else:
            transaction = Transaction(transaction_id, line_number)
            transactions[transaction_id] = transaction

        line_number += 1

line_number = 0
columns = {}
column_length = 60
last_transaction_id = None
max_column_number = 0

for line in lines:
    parts = line.split()
    if len(parts) > 3:
        line_id = parts[3]
        line_id_match = re.match(r'\[(\d+)-\d+\]', line_id)

        if line_id_match is not None:
            transaction_id = line_id_match.group(1)

        transaction = transactions[transaction_id]

        column_number = columns.get(transaction_id)
        if column_number is None:
            for i in range(len(columns)):
                if i not in columns.values():
                    column_number = i
                    break

            if column_number is None:
                column_number = len(columns)

            columns[transaction_id] = column_number

        last_column = sorted(columns.values())[-1]

        def truncate_statement(statement):
            return statement + ' ' * (column_length - len(statement))

        def transaction_start():
            return (' ' * (column_length/2 - 3)) + '######' + (' ' * (column_length/2 - 3))

        def transaction_end():
            return (' ' * (column_length/2 - 3)) + '======' + (' ' * (column_length/2 - 3))

        def transaction_space():
            return (' ' * (column_length/2 - 1)) + '..' + (' ' * (column_length/2 - 1))

        def print_row(active_column_callback):
            for i in range(last_column+1):
                if i == column_number:
                    column_str = active_column_callback()
                elif i in columns.values():
                    column_str = (' ' * (column_length/2 - 2)) + '....' + (' ' * (column_length/2 - 2))
                else:
                    column_str = ' ' * column_length

                sys.stdout.write(column_str)

            sys.stdout.write('\n')

        def print_statement():
            start_index = 7 if parts[6] == 'statement:' else 6
            statement = ' '.join(parts[start_index:])
            chunks = [statement[i:i+column_length] for i in range(0, len(statement), column_length)]

            for chunk in chunks:
                print_column_map('*')
                print_row(lambda: truncate_statement(chunk))

        def print_column_map(occupied_marker):
            for i in range(last_column+1):
                if i == column_number:
                    column_str = occupied_marker
                elif i in columns.values():
                    column_str = '.'
                else:
                    column_str = '_'

                sys.stdout.write(column_str)

            sys.stdout.write('|')

        if line_number == transaction.start:
            print_column_map('#')
            print_row(transaction_start)

        elif last_transaction_id == transaction.transaction_id:
            print_column_map('*')
            print_row(transaction_space)

        print_statement()

        if line_number == transaction.end:
            print_column_map('=')
            print_row(transaction_end)

            del columns[transaction_id]

        last_transaction_id = transaction.transaction_id
        line_number += 1