import asyncio
import json
import re
import requests
import pandas as pd
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from typing import Dict, List, Union, Optional, Any


next_delay = 0.1
players: Dict[int, Dict] = {}
error: List[Any] = []
players_with_errors: List[int] = []


def time_played_parser(time_string: str) -> int:
    """
    Parse a string to extract the time played as an integer.
    
    Args:
        time_string (str): The string containing the time played.
    
    Returns:
        int: Time played as an integer.
    """
    number = re.search(r'\d+', time_string)
    return int(number.group(0)) if number else 0


def get_cards(card_string: str) -> Dict[str, int]:
    """
    Parse a string to extract the number of cards.
    
    Args:
        card_string (str): The string containing card information.
    
    Returns:
        dict: A dictionary containing the number of yellow, yellowred and red cards.
    """
    c = [int(i) if i.isnumeric() else 0 for i in re.split(r'\s*/\s*', card_string)]
    return {'yellow': c[0], 'yellowred': c[1], 'red': c[2]}


def get_table_data(player_id: int, row_class: str, html: Any,
                   player: Dict[str, Union[str, int, List]]) -> None:
    """
    Populate the player dictionary with data from the html table.
    
    Args:
        player_id (int): The player's ID.
        row_class (str): The row class to find in the table.
        html (Any): The HTML content to parse.
        player (Dict): The player dictionary to populate.
    """
    table = html.find('table', {'class': 'items'})

    for row in table.find_all('tr', {'class': row_class}):
        zentriert = row.find_all('td', {'class': 'zentriert'})
        season = zentriert[0].text
        time_played = time_played_parser(
            row.find('td', {'class': 'rechts'}).text)

        league = row.find('td', {'class': 'hauptlink no-border-links'}).text
        club = row.find('td', {'class': 'hauptlink no-border-rechts zentriert'}
                        ).find('a').get('title')

        player['seasons'].append({
            'season': season,
            'club': club,
            'league': league,
            'games': int(zentriert[2].text) if zentriert[2].text.isnumeric() else 0,
            'goals': int(zentriert[3].text) if zentriert[3].text.isnumeric() else 0,
            'assists': int(zentriert[4].text) if zentriert[4].text.isnumeric() else 0,
            'cards': get_cards(zentriert[5].text),
            'time_played': time_played
        })


def get_player_data(player_id: int, html: Any) -> Dict[str, Union[str, int, List]]:
    """
    Parse the HTML content and extract player data.

    Args:
        player_id (int): The player's ID.
        html (Any): The HTML content to parse.

    Returns:
        dict: A dictionary containing player data.
    """
    name = html.find('h1').text.strip()
    age = html.find('span', {'itemprop': 'birthDate'}).text.strip()
    match = re.compile(r'\d{2}\.\d{2}\.\d{4}').search(age)
    birth_date = match.group(0) if match else None
    
    player = {'playerID': player_id, 'name': name, 'birth_date': birth_date, 'seasons': []}
    get_table_data(player_id, 'odd', html, player)
    get_table_data(player_id, 'even', html, player)
    return player


async def get_player_performance(player_id: int, session: ClientSession) -> None:
    """
    Asynchronously get a player's performance data from a website.

    Args:
        player_id (int): The player's ID.
        session (ClientSession): The aiohttp ClientSession to make the request.
    """
    global next_delay
    global players

    next_delay += 0.1
    await asyncio.sleep(next_delay)
    url = f'https://www.transfermarkt.de/test/leistungsdatendetails/spieler/{player_id}'

    try:
        async with session.get(url) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), 'html.parser')
                players[player_id] = get_player_data(player_id, soup)
            else:
                error.append((player_id, response.status))
                print(f'Error: {player_id}, {response.status}')
    except:
        players_with_errors.append(player_id)


async def get_players(player_ids: List[int]) -> None:
    """
    Asynchronously get performance data for a list of players.

    Args:
        player_ids (List[int]): List of player IDs.
    """
    async with ClientSession() as session:
        tasks = [get_player_performance(player_id, session) for player_id in player_ids]
        print(f'{len(tasks)} Tasks created')
        await asyncio.gather(*tasks)


def main() -> None:
    """
    Main function to start the data retrieval.
    """
    player_ids = []
    competitions = ['L1', 'GB1', 'ES1', 'IT1', 'FR1']

    for competition in competitions:
        data = pd.read_csv(f'players_{competition}.csv', header=None)
        player_ids.extend(data.iloc[:, 0].tolist())

    player_ids = sorted(set(player_ids))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_players(player_ids))

    with open("player_data.json", "w") as file:
        json.dump(players, file)

    requests.post("https://ntfy.sh/ajf_uws",
    data="scraping.py done".encode(encoding='utf-8'))

if __name__ == "__main__":
    main()
