import requests
from flask import Flask, request, jsonify
import logging
import random
from flask_ngrok import run_with_ngrok
from requests import get
from io import BytesIO

app = Flask(__name__)
run_with_ngrok(app)

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

sessionStorage = {}
id_image_del = []

default_form_dialog = [  # Стандартные кнопки для вывода
    {
        'title': 'Информация о личности',
        'hide': True

    },
    {
        'title': 'Информация об определении',
        'hide': True

    },
    {
        'title': 'Информация о дате',
        'hide': True

    },
    {
        'title': 'Информация о событии',
        'hide': True
    },
    {
        'title': 'Играть',
        'hide': True
    },
    {
        'title': 'Выйти из навыка',
        'hide': True
    }
]


def download(name_file):  # Скачивание изображений с api
    url = "https://dialogs.yandex.net/api/v1/skills/aad399e9-2c8a-4d76-a886-c50a13c03762/images"
    oauth_token = "y0_AgAAAAArJ24SAAT7owAAAADhQF7ai1jyRoPhTc2rXbjtYIvbPclQYYc"

    # Загружаем изображение с сайта
    response = requests.get(f'https://e3f7-46-236-191-178.ngrok-free.app/static/images/{name_file}')
    image_content = response.content

    # Загружаем изображение на сервер Яндекс.Диалогов
    headers = {
        "Authorization": f"OAuth {oauth_token}",
    }
    files = {
        "file": (name_file, BytesIO(image_content), "image/jpeg"),
    }
    response = requests.post(url, headers=headers, files=files)
    image_id = response.json()["image"]["id"]
    return image_id


def del_(id_image_del):  # Удаление изображений из внутренних ресурсов
    for image_id in id_image_del:
        url = "https://dialogs.yandex.net/api/v1/skills/aad399e9-2c8a-4d76-a886-c50a13c03762/images/" + image_id
        oauth_token = "y0_AgAAAAArJ24SAAT7owAAAADhQF7ai1jyRoPhTc2rXbjtYIvbPclQYYc"

        headers = {
            "Authorization": f"OAuth {oauth_token}",
        }
        response = requests.delete(url, headers=headers)


@app.route('/post', methods=['POST'])
def main():  # Создание запроса и получение ответа
    logging.info('Request: %r', request.json)

    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }

    handle_dialog(response, request.json)

    logging.info('Request: %r', response)

    return jsonify(response)


def handle_dialog(res, req):  # Основная стадия диалога, проверяющая, что ответил пользователь
    user_id = req['session']['user_id']

    if req['session']['new']:  # При появлении нового аккаунта все данные прошлого стираются
        res['response']['text'] = 'Привет! Назови свое имя!'
        sessionStorage[user_id] = {
            'first_name': None,
            'personalities': 0,
            'concepts': 0,
            'dates': 0,
            'events': 0,
            'game_stage': 0,
        }

        return

    first_name = get_first_name(req)

    if sessionStorage[user_id]['first_name'] is None:

        if first_name is None:  # Если в запросе не оказалось имени
            res['response']['text'] = 'Не раслышала имя. Повтори!'
        else:
            sessionStorage[user_id]['first_name'] = first_name
            sessionStorage[user_id]['guessed_concepts'] = []
            res['response']['text'] = 'Приятно познакомиться, ' + first_name.title() + '. Я справочник' \
                                                                                       ', могу рассказать вам о\
                                                                                        личности, дате или событии.\
                                                                                         Также можете поиграть в игру' \
                                                                                       ' "Угадайка".'
            res['response']['buttons'] = default_form_dialog

    else:

        if sessionStorage[user_id]['personalities'] == 0 and sessionStorage[user_id]['concepts'] == 0 and \
                sessionStorage[user_id]['events'] == 0 and sessionStorage[user_id]['dates'] == 0 \
                and sessionStorage[user_id]['game_stage'] == 0:
            # Проверка содержания ответа пользователя для продолжения диалога
            nlu_res = [i.lower() for i in req['request']['nlu']['tokens']]
            if 'помощь' in [i.lower() for i in req['request']['nlu']['tokens']]:
                res['response']['text'] = 'Вы можете выбрать то, о чем узнать: \
                 о личности, дате, событии или определении. А ткаже вы можете поиграть в невероятно веселую ' \
                                          'игру "Угадайка".'
                res['response']['buttons'] = default_form_dialog
            elif 'личности' in [i.lower() for i in req['request']['nlu']['tokens']]:
                sessionStorage[user_id]['personalities'] = 1
                personalities(res, req)
            elif 'нет' in [i.lower() for i in req['request']['nlu']['tokens']]:
                res['response']['text'] = 'Выберете любую функцию.'
                sessionStorage[user_id]['game_stage'] = 0
                res['response']['buttons'] = default_form_dialog
            elif 'определении' in [i.lower() for i in req['request']['nlu']['tokens']]:
                sessionStorage[user_id]['concepts'] = 1
                concepts(res, req)
            elif 'да' in [i.lower() for i in req['request']['nlu']['tokens']]:
                sessionStorage[user_id]['game_stage'] = 1
                sessionStorage[user_id]['attempt'] = 1
                game(res, req)
            elif 'дате' in [i.lower() for i in req['request']['nlu']['tokens']]:
                sessionStorage[user_id]['dates'] = 1
                dates(res, req)
            elif 'событии' in [i.lower() for i in req['request']['nlu']['tokens']]:
                sessionStorage[user_id]['events'] = 1
                events(res, req)
            elif 'играть' in nlu_res or 'игра' in nlu_res or 'отгадайка' in nlu_res or 'сыграть' in nlu_res:
                if len(sessionStorage[user_id]['guessed_concepts']) == 3:

                    res['response']['text'] = 'Ты отгадал все определения!'
                    sessionStorage[user_id]['game_stage'] = 0
                    res['response']['buttons'] = default_form_dialog
                else:

                    sessionStorage[user_id]['game_stage'] = 1
                    sessionStorage[user_id]['attempt'] = 1
                    game(res, req)
            elif 'выйти' in [i.lower() for i in req['request']['nlu']['tokens']]:
                del_(id_image_del)
                res['response']['text'] = 'Запускайте навык ещё. Всего самого наилучшего!'
                res['end_session'] = True
            elif 'перейти' in [i.lower() for i in req['request']['nlu']['tokens']]:
                # Завершение сеанса при переходе на сайт
                del_(id_image_del)
                res['response']['text'] = 'Запускайте навык ещё. Всего самого наилучшего!'
                res['end_session'] = True
            else:
                res['response']['text'] = 'Не поняла ответа! Если вы не поняли, что нужно делать для продолжения' \
                                          ' диалога, то можете сказать или выбрать помощь.'
                res['response']['buttons'] = [
                    {
                        'title': 'Помощь',
                        'hide': True
                    }
                ]
        elif 'помощь' in req['request']['original_utterance'].lower().split():
            if sessionStorage[user_id]['concepts'] == 1:
                concepts(res, req)
            elif sessionStorage[user_id]['personalities'] == 1:
                personalities(res, req)
            elif sessionStorage[user_id]['events'] == 1:
                events(res, req)
            elif sessionStorage[user_id]['dates'] == 1:
                dates(res, req)
            elif sessionStorage[user_id]['game_stage'] == 1:
                game(res, req)
            res['response']['text'] = 'На данном этапе вы можете выбать одну из предложенных функций или \
                                        же поиграть в любую игру на выбор.'
            res['response']['buttons'] = default_form_dialog
        else:
            if sessionStorage[user_id]['concepts'] == 1:
                concepts(res, req)
            elif sessionStorage[user_id]['personalities'] == 1:
                personalities(res, req)
            elif sessionStorage[user_id]['events'] == 1:
                events(res, req)
            elif sessionStorage[user_id]['dates'] == 1:
                dates(res, req)
            elif sessionStorage[user_id]['game_stage'] == 1:
                game(res, req)
            else:
                pass


def personalities(res, req):  # Обращение к api для получения информации о личности
    res['response']['text'] = 'О какой личности вам хотелось бы узнать?'
    user_id = req['session']['user_id']
    res['response']['buttons'] = [
        {
            'title': 'Выйти из навыка',
            'hide': True
        },
        {
            'title': 'Выбрать другую функцию',
            'hide': True
        }]
    if 'личности' not in req['request']['nlu']['tokens']:
        nlu_res = [i.lower() for i in req['request']['nlu']['tokens']]
        if 'выйти' in nlu_res or 'перейти' in nlu_res:
            res['response']['text'] = 'Запускайте навык ещё. Всего самого наилучшего!'
            del_(id_image_del)
            res['end_session'] = True
            return
        if 'выбрать' in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Конечно! О чем бы вы хотели узнать теперь?'
            res['response']['buttons'] = default_form_dialog
            sessionStorage[user_id]['personalities'] = 0
            return
        name = req['request']['original_utterance']
        api_information = get(f"https://e3f7-46-236-191-178.ngrok-free.app/api/personalities/title/{name}").json()
        if 'message' in api_information.keys():
            api_information = None
        if not api_information:
            res['response']['text'] = f'Простите, я ничего не знаю о {name}.'
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },
                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }
            ]
        else:
            res['response']['card'] = {}
            res['response']['card']['type'] = 'BigImage'
            res['response']['card'][
                'title'] = f"{api_information['personalities']['title']}" \
                           f": {api_information['personalities']['content']}"[:70] + "..."
            name_im = download(api_information['personalities']['title_image'])
            res['response']['card']['image_id'] = name_im
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },
                {
                    'title': 'Перейти на сайт для дальнейшего ознакомления',
                    'hide': True,
                    'url': 'https://e3f7-46-236-191-178.ngrok-free.app'
                },
                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }]


def concepts(res, req):  # Обращение к api для получения информации об определении
    res['response']['text'] = 'Какое определение вас интересует?'
    res['response']['buttons'] = [
        {
            'title': 'Выйти из навыка',
            'hide': True
        },
        {
            'title': 'Выбрать другую функцию',
            'hide': True
        }]
    user_id = req['session']['user_id']
    if 'определении' not in req['request']['nlu']['tokens']:
        if 'выйти' in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Запускайте навык ещё. Всего самого наилучшего!'
            del_(id_image_del)
            res['end_session'] = True
            return
        if 'выбрать' in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Конечно! О чем бы вы хотели узнать теперь?'
            res['response']['buttons'] = default_form_dialog
            sessionStorage[user_id]['concepts'] = 0
            return
        name = req['request']['original_utterance']
        api_information = get(f"https://e3f7-46-236-191-178.ngrok-free.app/api/concepts/title/{name}").json()
        if 'message' in api_information.keys():
            api_information = None
        if not api_information:  # Для работы с api, нужно заменить name на api_information
            res['response']['text'] = f'Простите, я ничего не знаю о {name}.'
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },
                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }]
        else:
            res['response']['card'] = {}
            res['response']['card']['type'] = 'BigImage'
            res['response']['card'][
                'title'] = f"{api_information['concepts']['title']}" \
                           f": {api_information['concepts']['content']}"[:70] + "..."
            name_im = download(api_information['concepts']['title_image'])
            res['response']['card']['image_id'] = name_im
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },
                {
                    'title': 'Перейти на сайт для дальнейшего ознакомления',
                    'hide': True,
                    'url': 'https://e3f7-46-236-191-178.ngrok-free.app'
                },
                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }]


def events(res, req):  # Обращение к api для получения информации о событии
    res['response']['text'] = 'Какое событие вас интересует?'
    user_id = req['session']['user_id']
    nlu_res = [i.lower() for i in req['request']['nlu']['tokens']]
    res['response']['buttons'] = [
        {
            'title': 'Выйти из навыка',
            'hide': True
        },
        {
            'title': 'Выбрать другую функцию',
            'hide': True
        }]
    if 'событии' not in req['request']['nlu']['tokens']:
        if 'выйти' in nlu_res or 'перейти' in nlu_res:
            res['response']['text'] = 'Запускайте навык ещё. Всего самого наилучшего!'
            del_(id_image_del)
            res['end_session'] = True
            return
        if 'выбрать' in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Конечно! О чем бы вы хотели узнать теперь? Или можете поиграть в "Угадайку".'
            res['response']['buttons'] = default_form_dialog
            sessionStorage[user_id]['events'] = 0
            return
        name = req['request']['original_utterance']
        api_information = get(f"https://e3f7-46-236-191-178.ngrok-free.app/api/events/title/{name}").json()
        if 'message' in api_information.keys():
            api_information = None
        if not api_information:
            res['response']['text'] = f'Простите, я ничего не знаю о {name}.'
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },

                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }]
        else:
            res['response']['card'] = {}
            res['response']['card']['type'] = 'BigImage'
            res['response']['card'][
                'title'] = f"{api_information['events']['title']}" \
                           f": {api_information['events']['content']}"[:70] + "..."
            name_im = download(api_information['events']['title_image'])
            res['response']['card']['image_id'] = name_im
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },
                {
                    'title': 'Перейти на сайт для дальнейшего ознакомления',
                    'hide': True,
                    'url': 'https://e3f7-46-236-191-178.ngrok-free.app'
                },
                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }]


def dates(res, req):  # Обращение к api для получения информации о дате
    res['response']['text'] = 'Какая дата вас интересует?'
    user_id = req['session']['user_id']
    res['response']['buttons'] = [
        {
            'title': 'Выйти из навыка',
            'hide': True
        },
        {
            'title': 'Выбрать другую функцию',
            'hide': True
        }]
    if 'дате' not in req['request']['nlu']['tokens']:
        if 'выйти' in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Запускайте навык ещё. Всего самого наилучшего!'
            del_(id_image_del)
            res['end_session'] = True
            return
        if 'выбрать' in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Конечно! О чем бы вы хотели узнать теперь?'
            res['response']['buttons'] = default_form_dialog
            sessionStorage[user_id]['dates'] = 0
            return
        name = get_date(req)
        if name:
            name = get_date(req)
        api_information = get(f"https://e3f7-46-236-191-178.ngrok-free.app/api/dates/date/{name}").json()
        if 'message' in api_information.keys():
            api_information = None
        if not api_information:
            res['response']['text'] = f'Простите, я ничего не знаю о {name}.'
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },
                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }]
        else:
            res['response']['text'] = \
                f"{','.join([date['title'] + ': ' + date['content'] for date in api_information['dates']])}"[:250]
            res['response']['buttons'] = [
                {
                    'title': 'Выйти из навыка',
                    'hide': True
                },
                {
                    'title': 'Выбрать другую функцию',
                    'hide': True
                }]


def game(res, req):  # Игра "Угадайка"
    user_id = req['session']['user_id']
    attempt = sessionStorage[user_id]['attempt']
    if attempt == 1:
        response = requests.get("https://e3f7-46-236-191-178.ngrok-free.app/api/concepts").json()['concepts']
        random_concepts = response[random.randint(0, len(response) - 1)]  # Выбор трёх случайных определений
        if random_concepts['title'][:-3].lower() in random_concepts['content'].lower():
            text = random_concepts['content'].split()
            for i in range(len(text)):
                if random_concepts['title'][:-3].lower() in text[i].lower():
                    text[i] = '...'
                    # Превращение упоминаний самого определения в троеточие, чтобы ответа не было в загадке
            random_concepts['content'] = ' '.join(text)
        while random_concepts['title'] in sessionStorage[user_id]['guessed_concepts']:
            random_concepts = response[random.randint(0, len(response) - 1)]
            if random_concepts['title'][:-3].lower() in random_concepts['content'].lower():
                text = random_concepts['content'].split()
                for i in range(len(text)):
                    if random_concepts['title'][:-3].lower() in text[i].lower():
                        text[i] = '...'
                random_concepts['content'] = ' '.join(text)
        sessionStorage[user_id]['game_concepts_title'] = random_concepts['title']
        sessionStorage[user_id]['game_concepts_content'] = random_concepts['content']
        sessionStorage[user_id]['game_concepts_image'] = random_concepts['title_image']

        res['response']['text'] = sessionStorage[user_id]['game_concepts_content']
    else:
        concepts = sessionStorage[user_id]['game_concepts_title']
        content = sessionStorage[user_id]['game_concepts_content']
        if concepts.lower() in [i.lower() for i in req['request']['nlu']['tokens']]:

            res['response']['text'] = 'Правильно! Сыграем еще?'
            res['response']['buttons'] = [
                {
                    'title': 'Играть еще',
                    'hide': True

                },
                {
                    'title': 'Нет',
                    'hide': True

                }
            ]
            sessionStorage[user_id]['guessed_concepts'].append(concepts)
            sessionStorage[user_id]['game_stage'] = 0
            return

        else:

            res['response']['text'] = 'Неправильно'
            if attempt == 3:
                res['response']['text'] = 'Вы пытались. Это ' + sessionStorage[user_id]['game_concepts_title'] \
                                          + '. Сыграем еще?'
                res['response']['buttons'] = [
                    {
                        'title': 'Да',
                        'hide': True

                    },
                    {
                        'title': 'Нет',
                        'hide': True

                    },
                ]
                sessionStorage[user_id]['game_stage'] = 0
                sessionStorage[user_id]['guessed_concepts'].append(concepts)
                return
            else:
                api_information = get(f"https://e3f7-46-236-191-178.ngrok-free.app/api/concepts/title"
                                      f"/{sessionStorage[user_id]['game_concepts_title']}").json()
                name_im = download(api_information['concepts']['title_image'])
                res['response']['text'] = f'Неправильно. У вас ещё одна попытка.'
                res['response']['card'] = {}
                res['response']['card']['type'] = 'BigImage'
                res['response']['card'][
                    'title'] = f'Неправильно! У вас ещё одна попытка. Вот вам подсказка в виде картинки:'
                res['response']['card']['image_id'] = name_im

    sessionStorage[user_id]['attempt'] += 1


def get_date(req):  # Получение даты в виде числа из словестного вида
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.DATETIME':
            if 'year' in entity['value'].keys():
                return entity['value']['year']
            else:
                return None
    return None


def get_first_name(req):  # Определение, является ли запрос именем
    for entity in req['request']['nlu']['entities']:

        if entity['type'] == 'YANDEX.FIO':

            if 'first_name' in entity['value'].keys():
                return entity['value']['first_name']
            else:
                return None
    return None


if __name__ == '__main__':
    app.run(port=8000, host='127.0.0.1')
