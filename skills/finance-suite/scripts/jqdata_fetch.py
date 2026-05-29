#!/usr/bin/env python3
"""JQData 数据获取模块 — 股票/ETF/场外基金/指数成分股"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

try:
    from jqdatasdk import (auth, get_price, get_fundamentals, query, finance,
                           get_query_count, get_security_info, get_index_stocks,
                           normalize_code, get_all_securities)
    JQDATA_AVAILABLE = True
except ImportError:
    JQDATA_AVAILABLE = False


class JQDataFetcher:

    def __init__(self):
        self.authenticated = False
        self.username = os.getenv('JQDATA_USERNAME', '')
        self.password = os.getenv('JQDATA_PASSWORD', '')

    def _ensure_auth(self) -> Optional[Dict]:
        if not self.authenticated:
            result = self.authenticate()
            if not result['success']:
                return result
        return None

    def authenticate(self) -> Dict[str, Any]:
        if not JQDATA_AVAILABLE:
            return {'success': False, 'error': 'jqdatasdk 未安装'}
        if not self.username or not self.password:
            return {'success': False, 'error': '未配置 JQDATA_USERNAME / JQDATA_PASSWORD'}
        try:
            auth(self.username, self.password)
            self.authenticated = True
            count = get_query_count()
            return {
                'success': True,
                'quota': {
                    'total': count.get('total', 0),
                    'used': count.get('spare', 0),
                    'remaining': count.get('total', 0) - count.get('spare', 0)
                }
            }
        except Exception as e:
            return {'success': False, 'error': f'认证失败: {e}'}

    def get_stock_price(self, code: str, start_date: str = None, end_date: str = None,
                        frequency: str = 'daily', fields: List[str] = None) -> Dict[str, Any]:
        """获取股票/ETF行情"""
        err = self._ensure_auth()
        if err:
            return err
        try:
            nc = normalize_code(code)
            if fields is None:
                fields = ['open', 'close', 'high', 'low', 'volume', 'money']
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            df = get_price(nc, start_date=start_date, end_date=end_date,
                           frequency=frequency, fields=fields)
            return {
                'success': True, 'code': nc,
                'data': df.reset_index().to_dict('records'),
                'count': len(df), 'start_date': start_date,
                'end_date': end_date, 'frequency': frequency
            }
        except Exception as e:
            return {'success': False, 'error': f'获取行情失败: {e}'}

    def get_stock_info(self, code: str) -> Dict[str, Any]:
        """获取证券基本信息（股票/ETF/基金均可）"""
        err = self._ensure_auth()
        if err:
            return err
        try:
            nc = normalize_code(code)
            info = get_security_info(nc)
            return {
                'success': True, 'code': nc,
                'name': info.display_name,
                'start_date': str(info.start_date),
                'end_date': str(info.end_date) if info.end_date else None,
                'type': info.type
            }
        except Exception as e:
            return {'success': False, 'error': f'获取证券信息失败: {e}'}

    def get_fund_nav(self, code: str, start_date: str = None, end_date: str = None,
                     limit: int = 20) -> Dict[str, Any]:
        """获取场外基金净值（6位基金代码，如 000001）"""
        err = self._ensure_auth()
        if err:
            return err
        try:
            fund_code = code.strip().split('.')[0].zfill(6)
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == fund_code
            )
            if start_date:
                q = q.filter(finance.FUND_NET_VALUE.day >= start_date)
            if end_date:
                q = q.filter(finance.FUND_NET_VALUE.day <= end_date)
            q = q.order_by(finance.FUND_NET_VALUE.day.desc()).limit(limit)
            df = finance.run_query(q)
            if df.empty:
                return {'success': False, 'error': f'未找到基金 {fund_code} 的净值数据'}
            records = df[['code', 'day', 'net_value', 'sum_value', 'refactor_net_value']].to_dict('records')
            return {
                'success': True, 'code': fund_code,
                'count': len(records), 'data': records,
                'note': 'net_value=单位净值 sum_value=累计净值 refactor_net_value=复权净值，按日期降序'
            }
        except Exception as e:
            return {'success': False, 'error': f'获取基金净值失败: {e}'}

    def get_fund_list(self, fund_type: str = 'etf') -> Dict[str, Any]:
        """获取基金列表（etf/lof/open_fund/money_market_fund）"""
        err = self._ensure_auth()
        if err:
            return err
        try:
            valid = ['etf', 'lof', 'fja', 'fjb', 'open_fund', 'money_market_fund']
            if fund_type not in valid:
                return {'success': False, 'error': f'fund_type 必须是: {", ".join(valid)}'}
            df = get_all_securities(types=[fund_type])
            records = df.reset_index().rename(columns={'index': 'code'}).to_dict('records')
            return {
                'success': True, 'fund_type': fund_type,
                'count': len(records), 'data': records[:100]
            }
        except Exception as e:
            return {'success': False, 'error': f'获取基金列表失败: {e}'}

    def get_fund_info(self, code: str) -> Dict[str, Any]:
        """获取场内基金（ETF/LOF）基本信息 + 近期行情"""
        err = self._ensure_auth()
        if err:
            return err
        try:
            nc = normalize_code(code)
            info = get_security_info(nc)
            # 使用固定的试用账号数据范围终点，避免超出权限
            end_date = '2026-02-02'
            start_date = '2026-01-23'
            df = get_price(nc, start_date=start_date, end_date=end_date,
                           frequency='daily', fields=['open', 'close', 'high', 'low', 'volume', 'money'])
            return {
                'success': True, 'code': nc,
                'name': info.display_name, 'type': info.type,
                'start_date': str(info.start_date),
                'recent_price': df.reset_index().to_dict('records')
            }
        except Exception as e:
            return {'success': False, 'error': f'获取基金信息失败: {e}'}

    def get_fundamentals_data(self, code: str, date: str = None) -> Dict[str, Any]:
        """获取财务数据"""
        err = self._ensure_auth()
        if err:
            return err
        try:
            nc = normalize_code(code)
            date = date or datetime.now().strftime('%Y-%m-%d')
            q = query(finance.STK_INCOME_STATEMENT).filter(
                finance.STK_INCOME_STATEMENT.code == nc
            )
            df = get_fundamentals(q, date=date)
            if df.empty:
                return {'success': False, 'error': '未找到财务数据'}
            return {'success': True, 'code': nc, 'date': date, 'data': df.to_dict('records')}
        except Exception as e:
            return {'success': False, 'error': f'获取财务数据失败: {e}'}

    def get_index_stocks_list(self, index_code: str, date: str = None) -> Dict[str, Any]:
        """获取指数成分股"""
        err = self._ensure_auth()
        if err:
            return err
        try:
            date = date or datetime.now().strftime('%Y-%m-%d')
            stocks = get_index_stocks(index_code, date=date)
            return {'success': True, 'index_code': index_code, 'date': date,
                    'stocks': list(stocks), 'count': len(stocks)}
        except Exception as e:
            return {'success': False, 'error': f'获取指数成分股失败: {e}'}


def main(action: str, **kwargs) -> Dict[str, Any]:
    fetcher = JQDataFetcher()
    actions = {
        'auth':         fetcher.authenticate,
        'price':        fetcher.get_stock_price,
        'info':         fetcher.get_stock_info,
        'fund_nav':     fetcher.get_fund_nav,
        'fund_list':    fetcher.get_fund_list,
        'fund_info':    fetcher.get_fund_info,
        'fundamentals': fetcher.get_fundamentals_data,
        'index_stocks': fetcher.get_index_stocks_list,
    }
    if action not in actions:
        return {'success': False, 'error': f'未知操作: {action}，可选: {", ".join(actions.keys())}'}
    if action == 'auth':
        return actions[action]()
    return actions[action](**kwargs)


if __name__ == '__main__':
    result = main('auth')
    print(json.dumps(result, ensure_ascii=False, indent=2))
