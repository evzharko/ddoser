#!/usr/bin/env python
import asyncio
import logging
from http import HTTPStatus
from typing import Iterable, List, Tuple, TextIO

import aiohttp
import click
import uvloop
from aiohttp_socks import ProxyConnector

from commons import config_logger, set_limits, load_proxies, Proxy


async def checker(
        proxy_iterator: Iterable[Proxy], check_url: str, result_proxy_file: TextIO, timeout: int
):
    timeout = aiohttp.ClientTimeout(total=timeout)
    for proxy in proxy_iterator:
        logging.info('Checking %s..', proxy)
        try:
            request_kwarg = {}
            if proxy.protocol in ('socks4', 'socks5'):
                connector = ProxyConnector.from_url(proxy.get_formatted())
                client_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            else:
                request_kwarg['proxy'] = proxy.get_formatted()
            async with client_session as session:
                async with session.get(check_url, **request_kwarg) as response:
                    if response.status == HTTPStatus.OK:
                        if (await response.text()).strip() == 'PONG':
                            logging.info('%s is OK', proxy.get_formatted())
                            result_proxy_file.write(f'{proxy}\n')
                            result_proxy_file.flush()
                        else:
                            logging.info('%s is bad: returns wrong data', proxy)
        except Exception as error:
            logging.info('%s is bad: %s (%s)', proxy.get_formatted(), type(error), error)


async def amain(
        proxies: List[Proxy], check_url: str, result_proxy_file: str, concurrency: int, timeout: int
):
    coroutines = []
    proxy_iterator = iter(proxies)
    with open(result_proxy_file, mode='w', encoding='utf8') as output:
        for _ in range(min(len(proxies), concurrency)):
            coroutines.append(checker(proxy_iterator, check_url, output, timeout))
        await asyncio.gather(*coroutines)


@click.command(help="Run ddoser")
@click.option('--proxy-url', help='url to proxy resourse', required=True)
@click.option('--check-url', help='url to resource that used to check proxy, should contains text "PONG"', required=True)
@click.option('--result-proxy-file', help='path to file with proxies have to be stored', required=True)
@click.option('--concurrency', help='concurrency level', type=int, default=1)
@click.option('--timeout', help='requests timeout', type=int, default=5)
@click.option('--protocol', help='override proxy format', type=click.Choice(['socks4', 'socks5', 'http', 'https'], case_sensitive=False))
@click.option('-v', '--verbose', help='Show verbose log', count=True)
@click.option('--log-to-stdout', help='log to console', is_flag=True)
def main(
        proxy_url: str, check_url: str, result_proxy_file: str,
        concurrency: int, timeout: int, protocol:str, verbose: bool, log_to_stdout: str
):
    config_logger(verbose, log_to_stdout)
    set_limits()
    uvloop.install()
    loop = asyncio.get_event_loop()
    proxies = load_proxies(None, proxy_url, protocol=protocol)
    loop.run_until_complete(amain(proxies, check_url, result_proxy_file, concurrency, timeout))

if __name__ == '__main__':
    main()
