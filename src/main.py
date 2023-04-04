import logging
import re
from urllib.parse import urljoin


from requests import RequestException
import requests_cache
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL, PEP_LIST_URL
from exceptions import ParserFindTagException
from outputs import control_output
from utils import find_tag, get_response, get_soup


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    soup = get_soup(session, whats_new_url)

    main_div = find_tag(soup, 'section', {'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', {'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li',
        attrs={'class': 'toctree-l1'}
    )

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        try:
            version_soup = get_soup(session, version_link)
            h1 = find_tag(version_soup, 'h1')
            dl = find_tag(version_soup, 'dl')
            dl_text = dl.text.replace('\n', ' ')
            results.append((version_link, h1.text, dl_text))
        except RequestException:
            logging.exception()
            break

    return results


def latest_versions(session):
    soup = get_soup(session, MAIN_DOC_URL)

    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    if a_tags is None:
        raise ParserFindTagException('Ничего не нашлось')

    results = []
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in tqdm(a_tags):
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append((link, version, status))

    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    soup = get_soup(session, downloads_url)

    table_tag = find_tag(soup, 'table')
    pdf_a4_tag = find_tag(
        table_tag,
        'a',
        attrs={'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    archive_url = urljoin(downloads_url, pdf_a4_tag['href'])

    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)

    archive_path = downloads_dir / filename
    response = get_response(session, archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    soup = get_soup(session, PEP_LIST_URL)

    section_tag = find_tag(soup, 'section', {'id': 'numerical-index'})
    body_tag = find_tag(section_tag, 'tbody')
    pep_tags = body_tag.find_all('tr')

    counter = {'Статус': 'Количество'}

    for pep in pep_tags:
        link_tag = find_tag(pep, 'a')
        pep_link = urljoin(PEP_LIST_URL, link_tag['href'])
        pep_soup = get_soup(session, pep_link)
        dt_tags = pep_soup.find_all('dt')
        for tag in dt_tags:
            if tag.text == 'Status:':
                status_tag = tag.next_sibling.next_sibling
                break

        if status_tag.text in counter:
            counter[status_tag.text] += 1
        else:
            counter[status_tag.text] = 1
        abbr_tag = find_tag(pep, 'abbr')
        abbr_status = abbr_tag.text[1:]
        if status_tag.text not in EXPECTED_STATUS[abbr_status]:
            logging.info(f'PEP{link_tag.text}: Статус в карточке ' +
                         'не совпал с ожидаемым. Ожидаемый: ' +
                         f'{EXPECTED_STATUS[abbr_status]}, в карточке: ' +
                         f'{status_tag.text}')

    counter['Total'] = len(pep_tags)
    return counter.items()


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    if parser_mode == 'pep':
        args.output = 'file'
    try:
        results = MODE_TO_FUNCTION[parser_mode](session)
    except ParserFindTagException:
        logging.exception()
    except RequestException:
        logging.exception()

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
