import React from 'react';
import api from './server_api';
import {BITMAX, BINANCE} from './config';

export class ExchangeRate extends React.Component {
    constructor (props) {
        super(props);
        this.state = {
            exchange_rate: null,
            status: 'loading'
        }
    }

    fetch_rate () {
        let ticker;
        if (window.stock === BITMAX) {
            ticker = 'BTC/USDT';
        } else if (window.stock === BINANCE) {
            ticker = 'BTCUSDT';
        }
        api.api_method('/get/rate', {
            params: {
                ticker: ticker,
            },
        }).then((
            (data) => {
                let exchange_rate = data.price;
                this.setState({
                    exchange_rate: exchange_rate,
                    status: 'loaded',
                    timestamp: Date.now(),
                });
            }
        ).bind(this)).catch((
            (error) => {
                console.error(error);
                this.setState({
                    status: 'error',
                });
            }
        ).bind(this));
    }

    componentDidMount () {
        this.fetch_rate();
        this.timer = setInterval((
            () => {
                this.fetch_rate();
            }
        ).bind(this), 1000 * 30);
    }

    componentWillUnmount () {
        clearInterval(this.timer);
    }

    render () {
        return (
            <div className='exchange_rate'>
                { this.state.status === 'loaded' && (
                    <span>
                        <span className="exchange_rate-span">
                            <span className="exchange_rate-span-rate">Курс</span>
                            <span>BTC/USDT = </span>
                        </span>
                        <span className="exchange_rate-rate">{this.state.exchange_rate}</span>
                        <Timer timestamp={this.state.timestamp}></Timer>
                    </span>
                ) }
                { this.state.status === 'loading' && (
                    <span>Загрузка</span>
                ) }
                { this.state.status === 'error' && (
                    <span>Нет подключения к боту</span>
                ) }
            </div>
        )
    }
}

class Timer extends React.Component {
    constructor (props) {
        super(props)
        this.state = {
            seconds_ago: 0,
        };
    }

    componentDidMount () {
        this.inter = setInterval((
            () => {
                let now = Date.now();
                this.setState({
                    seconds_ago: Math.round(
                        (now - this.props.timestamp) / 1000
                    ),
                });
            }
        ).bind(this), 1000);
    }

    componentWillUnmount () {
        clearInterval(this.inter);
    }

    get_word_for_second(seconds) {
        let num = seconds % 10;
        if (Math.floor(seconds / 10) === 1) {
            return 'секунд'
        } else if (num === 1) {
            return 'секунду'
        } else if ([2, 3, 4].includes(num)) {
            return 'секунды'
        } else {
            return 'секунд'
        }
    }

    render () {
        return (
            <span className='exchange_rate-time'>{this.state.seconds_ago} {this.get_word_for_second(this.state.seconds_ago)} назад</span>
        )
    }

}
