from bs4 import BeautifulSoup

from exceptions import ParserFindTagException


def get_response(session, url):
    response = session.get(url)
    response.encoding = 'utf-8'
    return response


def get_soup(session, url):
    response = get_response(session, url)
    return BeautifulSoup(response.text, features='lxml')


def find_tag(soup, tag, attrs=None):
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        raise ParserFindTagException(error_msg)
    return searched_tag
