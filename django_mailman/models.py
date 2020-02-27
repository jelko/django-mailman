# -*- coding: utf-8 -*-
import re, sys
from future.standard_library import install_aliases
install_aliases()
from urllib.parse import urlparse, urlencode
from urllib.request import urlopen, build_opener
from urllib.error import HTTPError
try:
    unicode('')
except NameError:
    unicode = str

import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _

from .webcall import MultipartPostHandler

logger = logging.getLogger(__name__)

# adding custom exceptions to deal with cases differently

class MailmanException(Exception):
    pass

class MailmanWarning(MailmanException):
    pass

class AlreadyAMemberException(MailmanWarning):
    pass

class NotAMemberException(MailmanWarning):
    pass

# You can find all local translations in the Mailman Repository in the messages folder
# https://bazaar.launchpad.net/~mailman-coders/mailman/2.1/view/head:/messages/

ALREADY_A_MEMBER_MSG = (
    u'Already a member', # en
    u'Bereits Mitglied', # de
    u'Déjà abonné', # fr
)

# Mailman-Messages for a successfull subscription
SUBSCRIBE_MSG = (
    u'Erfolgreich eingetragen', # de
    u'Successfully subscribed', # en
    u'Abonnement r\xe9ussi', # fr
)

# Mailman-Messages for successfully remove from a list
UNSUBSCRIBE_MSG = (
    u'Erfolgreich beendete Abonnements', # de
    u'Successfully Removed', # en
    u'Successfully Unsubscribed', # also en
    u'R\xe9siliation r\xe9ussie', # fr
)

# Mailman-Messages for a failed remove from a list
NON_MEMBER_MSG = (
    u'Nichtmitglieder können nicht aus der Mailingliste ausgetragen werden', # de
    u'Cannot unsubscribe non-members', # en
    u"Ne peut r\xe9silier l'abonnement de non-abonn\xe9s ", # fr
)

# To control user form unsubscription
UNSUBSCRIBE_BUTTON = {
    'fr' : 'Résilier',
}

# Definition from the Mailman-Source ../Mailman/Default.py
LANGUAGES = (
    ('utf-8',       _('Arabic')),
    ('utf-8',       _('Catalan')),
    ('iso-8859-2',  _('Czech')),
    ('iso-8859-1',  _('Danish')),
    ('iso-8859-1',  _('German')),
    ('us-ascii',    _('English (USA)')),
    ('iso-8859-1',  _('Spanish (Spain)')),
    ('iso-8859-15', _('Estonian')),
    ('iso-8859-15', _('Euskara')),
    ('iso-8859-1',  _('Finnish')),
    ('iso-8859-1',  _('French')),
    ('utf-8',       _('Galician')),
    ('utf-8',       _('Hebrew')),
    ('iso-8859-2',  _('Croatian')),
    ('iso-8859-2',  _('Hungarian')),
    ('iso-8859-15', _('Interlingua')),
    ('iso-8859-1',  _('Italian')),
    ('euc-jp',      _('Japanese')),
    ('euc-kr',      _('Korean')),
    ('iso-8859-13', _('Lithuanian')),
    ('iso-8859-1',  _('Dutch')),
    ('iso-8859-1',  _('Norwegian')),
    ('iso-8859-2',  _('Polish')),
    ('iso-8859-1',  _('Portuguese')),
    ('iso-8859-1',  _('Portuguese (Brazil)')),
    ('iso-8859-2',  _('Romanian')),
    ('koi8-r',      _('Russian')),
    ('utf-8',       _('Slovak')),
    ('iso-8859-2',  _('Slovenian')),
    ('utf-8',       _('Serbian')),
    ('iso-8859-1',  _('Swedish')),
    ('iso-8859-9',  _('Turkish')),
    ('utf-8',       _('Ukrainian')),
    ('utf-8',       _('Vietnamese')),
    ('utf-8',       _('Chinese (China)')),
    ('utf-8',       _('Chinese (Taiwan)')),
)

# POST-Data for a list subcription
SUBSCRIBE_DATA = {
    'subscribe_or_invite': '0',
    'send_welcome_msg_to_this_batch': '0',
    'notification_to_list_owner': '0',
    'adminpw': None,
    'subscribees_upload': None,
}

# POST-Data for a list removal
UNSUBSCRIBE_DATA = {
    'send_unsub_ack_to_this_batch': 0,
    'send_unsub_notifications_to_list_owner': 0,
    'adminpw': None,
    'unsubscribees_upload': None,
}

def check_encoding(value, encoding):
    try:
        # use original function if we are running python 2
        from types import UnicodeType
        if isinstance(value, UnicodeType) and encoding != 'utf-8':
            value = value.encode(encoding)
        if not isinstance(value, UnicodeType) and encoding == 'utf-8':
            value = unicode(value, errors='replace')
        return value
    except ImportError:
        # ignore re-encoding and checking entirely when we are running python 3 with native unicode strings
        return value

def decode_str(string, encoding):
    # added helper function to remove old Python 2 dependencies
    # keeping it backwards compatible

    try:
        return string.decode(encoding=encoding)
    except AttributeError:
        # FIXME this two way conversion is stupid
        # TODO check if works in Python 2
        return str(bytes(string, encoding=encoding), encoding=encoding)


class List(models.Model):
    name = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    main_url = models.URLField()
    encoding = models.CharField(max_length=20, choices=LANGUAGES)

    class Meta:
        verbose_name = 'List-Installation'
        verbose_name_plural = 'List-Installations'

    def __unicode__(self):
        return u'%s' % (self.name)

    def __parse_status_content(self, content):
        if not content:
            raise Exception('No valid Content!')

        m = re.search('(?<=<h5>).+(?=:[ ]{0,1}</h5>)', content)
        if m:
            msg = m.group(0).rstrip()
        else:
            m = re.search('(?<=<h3><strong><font color="#ff0000" size="\+2">)'+
                          '.+(?=:[ ]{0,1}</font></strong></h3>)', content)
            if m:
                msg = m.group(0)
            else:
                raise Exception('Could not find status message')

        m = re.search('(?<=<ul>\n<li>).+(?=\n</ul>\n)', content)
        if m:
            member = m.group(0)
            # try separate member status message from member info
            # see source for details: https://bazaar.launchpad.net/~mailman-coders/mailman/2.1/view/head:/Mailman/Cgi/admin.py#L1228
            try:
                member = member.split(" -- ")[1].strip()
            except IndexError:
                pass
        else:
            raise Exception('Could not find member-information')

        msg = decode_str(msg, self.encoding)
        member = decode_str(member, self.encoding)
        return (msg, member)

    def __parse_member_content(self, content, encoding='iso-8859-1'):
        if not content:
            raise Exception('No valid Content!')
        members = []
        letters = re.findall('letter=\w{1}', content)
        chunks = re.findall('chunk=\d+', content)
        input = re.findall('name=".+_realname" type="TEXT" value=".*" size="[0-9]+" >', content)
        for member in input:
            info = member.split('" ')
            email = re.search('(?<=name=").+(?=_realname)', info[0]).group(0)
            realname = re.search('(?<=value=").*', info[2]).group(0)
            email = decode_str(email, encoding)
            realname = decode_str(realname, encoding)
            members.append([realname, email])
        letters = set(letters)
        return (letters, members, chunks)

    def get_admin_moderation_url(self):
        return '%s/admindb/%s/?adminpw=%s' % (self.main_url, self.name,
                                              self.password)

    def subscribe(self, email, first_name=u'', last_name=u''):
        from email.utils import formataddr

        url = '%s/admin/%s/members/add' % (self.main_url, self.name)

        first_name = check_encoding(first_name, self.encoding)
        last_name = check_encoding(last_name, self.encoding)
        email = check_encoding(email, self.encoding)
        name = '%s %s' % (first_name, last_name)

        SUBSCRIBE_DATA['adminpw'] = self.password
        SUBSCRIBE_DATA['subscribees_upload'] = formataddr([name.strip(), email])
        encoded_data = urlencode(SUBSCRIBE_DATA).encode(self.encoding)
        opener = build_opener(MultipartPostHandler(self.encoding, True))

        content = opener.open(url, encoded_data).read()

        (msg, member) = self.__parse_status_content(decode_str(content, self.encoding))
        if msg not in SUBSCRIBE_MSG:
            error = u'%s: %s' % (msg, member)
            print(member)
            if member in ALREADY_A_MEMBER_MSG:
                raise AlreadyAMemberException(error.encode(self.encoding))
            raise MailmanException(error.encode(self.encoding))

    def unsubscribe(self, email):
        url = '%s/admin/%s/members/remove' % (self.main_url, self.name)

        email = check_encoding(email, self.encoding)
        UNSUBSCRIBE_DATA['adminpw'] = self.password
        UNSUBSCRIBE_DATA['unsubscribees_upload'] = email
        opener = build_opener(MultipartPostHandler(self.encoding))
        encoded_data = urlencode(UNSUBSCRIBE_DATA).encode(self.encoding)
        content = opener.open(url, encoded_data).read()

        (msg, member) = self.__parse_status_content(decode_str(content, self.encoding))
        if (msg not in UNSUBSCRIBE_MSG):
            error = u'%s: %s' % (msg, member)
            if msg not in NON_MEMBER_MSG:
                raise NotAMemberException(error.encode(self.encoding))
            raise MailmanException(error.encode(self.encoding))

    def get_all_members(self):
        url = '%s/admin/%s/members/list' % (self.main_url, self.name)
        data = { 'adminpw': self.password }
        opener = build_opener(MultipartPostHandler(self.encoding))

        all_members = []
        encoded_data = urlencode(data).encode(self.encoding)
        try:
            content = opener.open(url, encoded_data).read()
            content = content.decode(self.encoding)
        except HTTPError as error:
            logger.error("%s %s" % (error, url))
            return []
    
        (letters, members, chunks) = self.__parse_member_content(content, self.encoding)
        all_members.extend(members)
        for letter in letters:
            url_letter = u"%s?%s" %(url, letter)
            content = opener.open(url_letter, encoded_data).read()
            (letters, members, chunks) = self.__parse_member_content(content, self.encoding)
            all_members.extend(members)
            for chunk in chunks[1:]:
                url_letter_chunk = "%s?%s&%s" %(url, letter, chunk)
                content = opener.open(url_letter_chunk, encoded_data).read()
                (letters, members, chunks) = self.__parse_member_content(content, self.encoding)
                all_members.extend(members)

        members = {}
        for m in all_members:
            email = m[1].replace(u"%40", u"@")
            members[email] = m[0]
        all_members = [(email, name) for email, name in members.items()]
        all_members.sort()
        return all_members

    def user_subscribe(self, email, password, language='fr', first_name=u'', last_name=u''):

        url = '%s/subscribe/%s' % (self.main_url, self.name)

        password = check_encoding(password, self.encoding)
        email = check_encoding(email, self.encoding)
        first_name = check_encoding(first_name, self.encoding)
        last_name = check_encoding(last_name, self.encoding)
        name = '%s %s' % (first_name, last_name)

        SUBSCRIBE_DATA['email'] = email
        SUBSCRIBE_DATA['pw'] = password
        SUBSCRIBE_DATA['pw-conf'] = password
        SUBSCRIBE_DATA['fullname'] = name
        SUBSCRIBE_DATA['language'] = language
        opener = build_opener(MultipartPostHandler(self.encoding, True))
        encoded_data = urlencode(SUBSCRIBE_DATA).encode(self.encoding)
        request = opener.open(url, encoded_data)
        content = request.read()
        for status in SUBSCRIBE_MSG:
            if len(re.findall(status, content)) > 0:
                return True
        raise MailmanException(content)

    def user_subscribe(self, email, password, language='fr', first_name=u'', last_name=u''):

        url = '%s/subscribe/%s' % (self.main_url, self.name)

        password = check_encoding(password, self.encoding)
        email = check_encoding(email, self.encoding)
        first_name = check_encoding(first_name, self.encoding)
        last_name = check_encoding(last_name, self.encoding)
        name = '%s %s' % (first_name, last_name)

        SUBSCRIBE_DATA['email'] = email
        SUBSCRIBE_DATA['pw'] = password
        SUBSCRIBE_DATA['pw-conf'] = password
        SUBSCRIBE_DATA['fullname'] = name
        SUBSCRIBE_DATA['language'] = language
        opener = build_opener(MultipartPostHandler(self.encoding, True))
        encoded_data = urlencode(SUBSCRIBE_DATA).encode(self.encoding)
        request = opener.open(url, encoded_data)
        content = request.read()
        # no error code to process

    def user_unsubscribe(self, email, language='fr'):

        url = '%s/options/%s/%s' % (self.main_url, self.name, email)

        email = check_encoding(email, self.encoding)

        UNSUBSCRIBE_DATA['email'] = email
        UNSUBSCRIBE_DATA['language'] = language
        UNSUBSCRIBE_DATA['login-unsub'] = UNSUBSCRIBE_BUTTON[language]
        
        opener = build_opener(MultipartPostHandler(self.encoding, True))
        encoded_data = urlencode(UNSUBSCRIBE_DATA).encode(self.encoding)
        request = opener.open(url, encoded_data)
        content = request.read()
        # no error code to process
