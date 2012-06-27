#!/usr/bin/env python2
#
# Copyright (C) 2008-2012  W. Trevor King
# Copyright (C) 2012-2013  Wade Berrier
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""LDAP address searches for Mutt.

Add :file:`mutt-ldap.py` to your ``PATH`` and add the following line
to your :file:`.muttrc`::

  set query_command = "mutt-ldap.py '%s'"

Search for addresses with `^t`, optionally after typing part of the
name.  Configure your connection by creating :file:`~/.mutt-ldap.rc`
contaning something like::

  [connection]
  server = myserver.example.net
  basedn = ou=people,dc=example,dc=net

See the `CONFIG` options for other available settings.
"""

import email.utils
import itertools
import os.path
import ConfigParser

import ldap
import ldap.sasl


CONFIG = ConfigParser.SafeConfigParser()
CONFIG.add_section('connection')
CONFIG.set('connection', 'server', 'domaincontroller.yourdomain.com')
CONFIG.set('connection', 'port', '389')  # set to 636 for default over SSL
CONFIG.set('connection', 'ssl', 'no')
CONFIG.set('connection', 'starttls', 'no')
CONFIG.set('connection', 'basedn', 'ou=x co.,dc=example,dc=net')
CONFIG.add_section('auth')
CONFIG.set('auth', 'user', '')
CONFIG.set('auth', 'password', '')
CONFIG.set('auth', 'gssapi', 'no')
CONFIG.add_section('query')
CONFIG.set('query', 'filter', '') # only match entries according to this filter
CONFIG.set('query', 'search_fields', 'cn displayName uid mail') # fields to wildcard search
CONFIG.add_section('results')
CONFIG.set('results', 'optional_column', '') # mutt can display one optional column
CONFIG.read(os.path.expanduser('~/.mutt-ldap.rc'))

def connect():
    protocol = 'ldap'
    if CONFIG.getboolean('connection', 'ssl'):
        protocol = 'ldaps'
    url = '{0}://{1}:{2}'.format(
        protocol,
        CONFIG.get('connection', 'server'),
        CONFIG.get('connection', 'port'))
    connection = ldap.initialize(url)
    if CONFIG.getboolean('connection', 'starttls') and protocol == 'ldap':
        connection.start_tls_s()
    if CONFIG.getboolean('auth', 'gssapi'):
        sasl = ldap.sasl.gssapi()
        connection.sasl_interactive_bind_s('', sasl)
    else:
        connection.bind(
            CONFIG.get('auth', 'user'),
            CONFIG.get('auth', 'password'),
            ldap.AUTH_SIMPLE)
    return connection

def search(query, connection=None):
    local_connection = False
    try:
        if not connection:
            local_connection = True
            connection = connect()
        post = ''
        if query:
            post = '*'
        filterstr = u'(|{0})'.format(
            u' '.join([u'({0}=*{1}{2})'.format(field, query, post)
                       for field in CONFIG.get('query', 'search_fields').split()]))
        query_filter = CONFIG.get('query', 'filter')
        if query_filter:
            filterstr = u'(&({0}){1})'.format(query_filter, filterstr)
        r = connection.search_s(
            CONFIG.get('connection', 'basedn'),
            ldap.SCOPE_SUBTREE,
            filterstr.encode('utf-8'))
    finally:
        if local_connection and connection:
            connection.unbind()
    return r

def format_columns(address, data):
    yield address
    yield data.get('displayName', data['cn'])[-1]
    optional_column = CONFIG.get('results', 'optional_column')
    if optional_column in data:
        yield data[optional_column][-1]

def format_entry(entry):
    cn,data = entry
    if 'mail' in data:
        for m in data['mail']:
            # http://www.mutt.org/doc/manual/manual-4.html#ss4.5
            # Describes the format mutt expects: address\tname
            yield "\t".join(format_columns(m, data))


if __name__ == '__main__':
    import sys

    query = unicode(' '.join(sys.argv[1:]), 'utf-8')
    entries = search(query)
    addresses = list(itertools.chain(
            *[format_entry(e) for e in sorted(entries)]))
    print('{0} addresses found:'.format(len(addresses)))
    print('\n'.join(addresses))
