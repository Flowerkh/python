# -*- coding: utf-8 -*-
"""
작성자: 반현오
작성일: 2023.08.18
용도 : Database Connection을 관리하기 위한 모듈
참고 : MySQL Connector/Python: https://dev.mysql.com/doc/connector-python/en/connector-python-introduction.html
"""

import os
import mysql.connector
from flask import abort, make_response
from lib.common import to_dictionary, err_print

db_host = os.environ.get('SQL_HOST')
db_user = os.environ.get('SQL_USERNAME')
db_password = os.environ.get('SQL_PASSWORD')
db_name = os.environ.get('SQL_DATABASE_NAME')
db_connection_name = os.environ.get('SQL_CONNECTION_NAME')


class ResultClass:
    """
    MySQL Return Class로 lib/db.py에서 실행 결과를 리턴할 때 사용한다.
    """

    def __init__(self):
        self.rowcount = None
        self.statement = None
        self.description = None
        self.rows = None
        self.column_names = None
        self.lastrowid = None
        self.error = None

    def set_from_cursor(self, cursor):
        # pprint(cursor.__dict__)

        self.rowcount = cursor.rowcount
        self.statement = cursor.statement
        self.description = cursor.description

        if (cursor.with_rows):  # select
            self.column_names = cursor.column_names
        else:  # insert, delete, update
            self.lastrowid = cursor.lastrowid

    def set_error(self, err):
        self.error = {'errno': err.errno,
                      'sqlstate': err.sqlstate, 'msg': err.msg}


def get_db(conn):
    try:
        if conn == 'b2b':
            db_host = 'mbp-prd-dtc-core-agreement.css3utrm7nlw.ap-northeast-2.rds.amazonaws.com'
            db_user = 'macrogen'
            db_password = 'dtccore240731#$%'
            db_name = 'b2bapi'

        elif conn == 'mgs':
            db_host = 'mbp-prd-dtc-core-agreement.css3utrm7nlw.ap-northeast-2.rds.amazonaws.com'
            db_user = 'macrogen'
            db_password = 'dtccore240731#$%'
            db_name = 'mygenome'

        elif conn == 'anal':
            db_host = 'rds-gentok-prd-analysis-mgmt.css3utrm7nlw.ap-northeast-2.rds.amazonaws.com'
            db_user = 'macrogen'
            db_password = 'dtccore240731#$%'
            db_name = 'b2bapi'

        # if conn=='b2b':
        #     db_host = '172.20.0.71'
        #     db_user = 'b2bapi'
        #     db_password = 'B2b!Q2w3e4r'
        #     db_name = 'b2bapi'

        # elif conn=='mgs':
        #     db_host = '172.20.0.71'
        #     db_user = 'mygenome'
        #     db_password = 'mg!Q2w3e4r'
        #     db_name = 'mygenome'

        db_config = {'user': db_user, 'passwd': db_password, 'charset': 'utf8',
                     'host': db_host, 'database': db_name, 'port': '3307'}

        db = mysql.connector.connect(**db_config)
        return db
    except mysql.connector.Error as err:
        err_print('DB Error', err)
        abort(make_response(err.msg, 500))


def queryall(conn, sql, param=()):
    result = ResultClass()
    try:
        db = get_db(conn)
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute(sql, param, multi=False)
        result.set_from_cursor(cursor)
        result.rows = cursor.fetchall()

    except mysql.connector.Error as err:
        err_print('DB Error', err)
        result.set_error(err)
    finally:
        cursor.close()
        db.close()

    return result


def queryone(conn, sql, param=()):
    result = ResultClass()
    try:
        db = get_db(conn)
        # buffered=True 가 없으면 mysql.connector.errors.InternalError: Unread result found 발생함.
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute(sql, param, multi=False)
        result.set_from_cursor(cursor)
        result.rows = cursor.fetchone()
    except mysql.connector.Error as err:
        err_print('DB Error', err)
        result.set_error(err)
    finally:
        cursor.close()
        db.close()

    return result


def execute(conn, sql, param=()):
    result = ResultClass()
    try:
        db = get_db(conn)
        cursor = db.cursor(dictionary=True)
        cursor.execute(sql, param, multi=False)
        result.set_from_cursor(cursor)

        if (cursor.with_rows):  # select
            result.rows = cursor.fetchall()
        else:
            db.commit()

    except mysql.connector.Error as err:
        err_print('DB Error', err)
        result.set_error(err)
    finally:
        cursor.close()
        db.close()

    return result


def callproc(conn, sql, param=()):
    result = ResultClass()

    try:
        db = get_db(conn)
        cursor = db.cursor(dictionary=True)
        cursor.callproc(sql, param)
        rows = []
        for sub_cursor in cursor.stored_results():
            # data = result.fetchall()
            data = to_dictionary(sub_cursor.fetchall(),
                                 sub_cursor.column_names)
            result.set_from_cursor(sub_cursor)
            # print(data)
            rows.append(data)
        result.rows = rows
    except mysql.connector.Error as err:
        err_print('DB Error', err)
        result.set_error(err)
    finally:
        cursor.close()
        db.close()

    return result


def update_with_pk(table_name, column_name, column_value, pk_column, pk_value):
    sql = 'UPDATE `{}` SET `{}` = %s WHERE `{}` = %s'.format(
        table_name, column_name, pk_column)
    return execute(sql, (column_value, pk_value))
