import os
import pickle
import re
import sys

from requests_html import HTMLSession
from tqdm import tqdm

sys.path.append('..')

session = HTMLSession()

extract_uid_from_url = lambda url: url.split('/')[-1]

is_valid_uid = lambda uid: re.match(r'[a-z0-9]{20,}', uid) is not None


def extract_article_from_database(database):
    data = {}
    for user_record in database.data:
        if 'data' in user_record:
            user_data = user_record['data']
            for user_data_record in user_data:
                if user_data_record['type'] in ['翻译', '校对']:
                    if 'juejin.im' not in user_data_record['article']['url']:
                        continue
                    uid = extract_uid_from_url(user_data_record['article']['url'])
                    if not is_valid_uid(uid):
                        continue
                    if uid not in data:
                        data[uid] = {'title': user_data_record['article']['name']}
                    if user_data_record['type'] == '翻译':
                        data[uid]['translate'] = user_data_record['integral']
                    else:
                        if 'proofread' not in data[uid]:
                            data[uid]['proofread'] = []
                        else:
                            data[uid]['proofread'].append(user_data_record['integral'])
    return data


def main():
    print('Load data...')
    data = pickle.load(open('../db.bin', 'rb'))
    print('Extract article information...')
    data = extract_article_from_database(data)
    print('Save article data...')
    pickle.dump(data, open('article.bin', 'wb'))
    print('Start fetch content from juejin.im and github.com')
    with tqdm(total=len(data)) as bar:
        for article_uid in list(data.keys()):
            # To reduce server load, do not use asynchronous here.
            # time.sleep(.8)
            if os.path.exists('./data/' + article_uid):
                bar.update()
                continue
            juejin_url = 'https://juejin.im/post/' + article_uid
            res = session.get(juejin_url)
            github_urls = list(filter(lambda url: 'gold-miner/blob' in url, res.html.links))
            if len(github_urls) > 0:
                github_url = github_urls[0]
            else:
                # github link not exist as a hyperlink but text
                github_urls = re.compile('本文永久链接(.+\.md)').findall(res.text)
                if len(github_urls) > 0:
                    github_url = github_urls[0]
                else:
                    print('Something wrong[1] with ' + article_uid)
                    bar.update()
                    continue
            github_file_path = github_url.split('blob/master')[-1]
            github_commit_history_api = 'https://api.github.com/repos/xitu/gold-miner/commits?path=' + github_file_path
            github_commit_history = session.get(github_commit_history_api,
                                                headers={'Authorization': 'token %s' % open("secret").read()}
                                                ).json()
            try:
                github_commit_history = list(map(lambda commit: commit['sha'], github_commit_history))
            except TypeError:
                print('Something wrong[2] with ' + article_uid)
                bar.update()
                continue
            for commit_sha in github_commit_history[::-1]:
                github_content_url = 'https://raw.githubusercontent.com/xitu/gold-miner/' + commit_sha + github_file_path
                file_content = session.get(github_content_url)
                if file_content.text.count('\n') > 10:
                    open('./data/' + article_uid, 'w').write(file_content.text)
                    break
            else:
                print('Something wrong[3] with ' + article_uid)
            bar.update()


if __name__ == '__main__':
    main()
