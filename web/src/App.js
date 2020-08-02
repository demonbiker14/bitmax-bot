import React from 'react';
import api from './server_api';
import store from './store';
import { reducer, updated_symbols } from './redux_utils';
import { Provider } from 'react-redux';
import OrderList, {NewOrder} from './OrderList';
import { ButtonList, NewButton } from './ButtonList';
import SymbolList from './SymbolList';
import { ExchangeRate } from './ExchangeRate';
import { app_context } from './context';
import {ImportExport} from './ImportExport';



class App extends React.Component {

    change_page (page_name, symbol=null) {
        let new_state = this.state;
        new_state.page_name = page_name;
        this.setState(new_state);
    }
    toggleMenu() {
        let state = this.state;
        state['menu_closed'] = !state['menu_closed'];
        this.setState(state);
    }
    constructor (props){
        super(props);
        this.state = {
            menu_closed: true,
            page_name: 'list-orders',
        }
        this.app_context = app_context;
        this.change_page = this.change_page.bind(this)
    }

    render () {
        let className = 'wrapper';
        if (this.state['menu_closed']) {
            className += ' menu_closed';
        }
        return (
            <Provider store={store}>
                <div className={className}>
                    <Menu
                        change_page={this.change_page}
                    ></Menu>
                    <Main
                        page_name={this.state.page_name}
                        symbol={this.state.symbol}
                        change_page={this.change_page}
                        toggleMenu={this.toggleMenu.bind(this)}
                        page_name={this.state.page_name}
                    ></Main>
                </div>
            </Provider>
        )
    }
}

class Menu extends React.Component {

    render () {
        let content = (
            <nav className="menu">
                <h1 className="global_title">Бот</h1>
                <button className="menu__page_option-button" type="button" onClick={
                    ()=>this.props.change_page('list-orders')
                }>Ордеры</button>
                <button className="menu__page_option-button" type="button" onClick={
                    ()=>this.props.change_page('list-symbols')
                }>Пары</button>
                <button className="menu__page_option-button" type="button" onClick={
                    ()=>this.props.change_page('list-buttons')
                }>Кнопки</button>
                <ImportExport></ImportExport>
            </nav>
        )
        return content
    }
}

class Main extends React.Component {

    constructor (props) {
        super(props)
        this.state = {
        }

    }

    render () {
        let content;
        if (this.props.page_name === 'list-orders') {

             content = (
                 <main className="content">
                     <ExchangeRate></ExchangeRate>
                     <OrderList change_page={this.props.change_page}></OrderList>
                 </main>
            )

        } else if (this.props.page_name === 'new_order')  {

            content = (
                <main className="content">
                    <NewOrder change_page={this.props.change_page}></NewOrder>
                </main>
            );

        } else if (this.props.page_name === 'symbol_page') {

            content = (
                <main className="content">
                    <OrderList
                        page_name={this.props.page_name}
                        change_page={this.props.change_page}
                    ></OrderList>
                </main>
            );

        } else if (this.props.page_name === 'list-buttons') {

            content = (
                <main className="content">
                    <ButtonList change_page={this.props.change_page}></ButtonList>
                </main>
            )

        } else if (this.props.page_name === 'new_button')  {

            content = (
                <main className="content">
                    <NewButton change_page={this.props.change_page}></NewButton>
                </main>
            );

        } else {

            content = (
                <main className="content">
                    <SymbolList></SymbolList>
                </main>
            );
        }

        return (
            <div className="main">
                <Header toggleMenu={this.props.toggleMenu}></Header>
                { content }
            </div>
        )

    }
}

class Header extends React.Component {

    render () {
        return (
            <header className="header">
                <div className="header-show_menu">
                    <button onClick={this.props.toggleMenu}>
                        <i className="fas fa-bars"></i>
                    </button>
                </div>
            </header>
        )
    }
}

export default App;
