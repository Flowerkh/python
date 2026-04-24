# -*- coding: utf-8 -*-
import json
import os

from flask import Blueprint, send_file, request, jsonify, Response
from http import HTTPStatus
from datetime import date, timedelta, datetime

from lib.db import queryone, queryall
from lib.util import authenticate, log_http_request_response, get_holiday_count_include_start_date, add_holiday_calc, \
    get_check_pdf_cache, insert_check_pdf_cache, serialize_for_json
from collections import defaultdict

# from lib.db import execute
# from lib.util import is_production_server, is_local_server, request_logging, now, compare_between_dates

bp = Blueprint('v1_api', __name__)


@bp.route('/')
def bp_index():
    return "Hello World v1", HTTPStatus.OK


@bp.route('/check_old', methods=['POST'])
# @request_logging
@authenticate
def bp_post_check_old():
    """
    1. 입력받은 json에서 ci의 유무 확인

    2. tb_agreement_user에서 di 조건으로 값 조회
       b2borderList_v7에서 ci 조건으로 값 조회 (kit_id는 2가 있으면 2, 아니면 1)

    3. 2의 결과로 mgs.tb_sale_orders 조회

    4. 2와 3의 교집합을 구하여 pdf 존재여부 파악

    5. pdf가 존재한다면 response를 작성
    """

    request_date = datetime.now()  # 요청 시간 기록
    data = request.json
    pdf_cache_data = json.dumps(data)
    request_info = get_check_pdf_cache(pdf_cache_data)

    if request_info == '':
        # 1. 입력받은 json에서 ci의 유무 확인
        data = request.json
        di = data.get('di', None)
        ci = data.get('ci', None)
        coworker_name = data.get('coworker_name', None)
        service = data.get('service', None)
        # user_collect_date = data.get('user_collect_date', None)
        product_code = data.get('product_code', None)
        user_name = data.get('user_name', None)
        gentok_order_code = data.get('gentok_order_code', None)
        kit_id = data.get('kit_id', None)

        if not di:
            json_msg = {"error": "di is required"}
            log_http_request_response(json_msg, HTTPStatus.BAD_REQUEST, request_date)
            return jsonify(json_msg), HTTPStatus.BAD_REQUEST

        select_query_1 = '''
            SELECT IFNULL(( SELECT DISTINCT IFNULL(kitID_2, kitID_1) FROM vw_b2borderList_all_no_bs WHERE kitID_1 = tau.kitid ), tau.kitid) AS kit_id
                   , tau.platform_order_code AS gentok_order_code
                   , tau.agreement_num
                   , tau.user_name
                   , tau.productCode as product_code
                   , CASE
                         WHEN tcc.coworker = tau.coworker THEN 'gentok'
                         ELSE tau.coworker
                     END AS coworker_name
                   , tau.user_collect_date
                   , tau.service
              FROM tb_agreement_user tau
              LEFT JOIN tb_coworker_content tcc
                     ON tau.coworker = tcc.coworker
                    AND tcc.id = 'is_gentok_sub_coworker' 
                    AND tcc.content = '1' 
                    AND tcc.service = 'genome'
                    AND tcc.a_type = 'common'
             WHERE 1=1
               AND tau.user_cert_di = %s
               AND tau.del = '0'
        '''

        select_query_2 = '''
            SELECT IFNULL(`kitID_2`, `kitID_1`) AS kit_id
                   , NULL AS gentok_order_code
                   , '0' as agreement_num
                   , client_name as user_name
                   , product_code
                   , coworker_name
                   , IFNULL(`lims_collected_date_2`, `lims_collected_date_1`) AS `user_collect_date`
                   , 'genome' as service
              FROM b2borderList_v7
             WHERE 1=1
               AND coworker_clientKey = %s
               AND requestStatus = '04'
               AND del IS NULL
        '''

        params_1 = [di, ]
        params_2 = [ci, ]

        # 파라미터에 따라 query where 조건 변경
        if coworker_name is not None:
            select_query_1 += " AND tau.coworker = %s"
            select_query_2 += " AND coworker_name = %s"
            params_1.append(coworker_name)
            params_2.append(coworker_name)

        if service is not None:
            if service == "genome":
                select_query_1 += " AND tau.service = 'genome'"
            elif service == "biome":
                select_query_1 += " AND r.service IN ('biome', 'thebiome')"

        if product_code is not None:
            select_query_1 += " AND tau.productCode = %s"
            select_query_2 += " AND product_code = %s"
            params_1.append(product_code)
            params_2.append(product_code)

        if user_name is not None:
            select_query_1 += " AND tau.user_name = %s"
            select_query_2 += " AND client_name = %s"
            params_1.append(user_name)
            params_2.append(user_name)

        if gentok_order_code is not None:
            select_query_1 += " AND tau.platform_order_code = %s"
            params_1.append(gentok_order_code)

        if kit_id is not None:
            select_query_1 += " AND r.kit_id = %s"
            select_query_2 += " AND r.kit_id = %s"
            params_1.append(kit_id)
            params_2.append(kit_id)

        # 2. tb_agreement_user에서 di 조건으로 값 조회
        #    b2borderList_v7에서 ci 조건으로 값 조회 (kit_id는 2가 있으면 2, 아니면 1)

        # TODO: AND tau.service = 'genome' 고쳐야 함.
        tau_result = queryall('b2b', select_query_1, params_1)
        v7_result = queryall('b2b', select_query_2, params_2)
        combined_result = tau_result.rows + v7_result.rows

        if len(combined_result) == 0:
            json_msg = {"message": "not found"}
            log_http_request_response(json_msg, HTTPStatus.NOT_FOUND, request_date)
            return jsonify(json_msg), HTTPStatus.NOT_FOUND

        list_ord_smpl_nm = []
        for item in combined_result:
            agreement_num = item['agreement_num']
            if agreement_num == '0':
                ord_smpl_nm = item['kit_id']
            else:
                ord_smpl_nm = f"{item['kit_id']}-{agreement_num}"
            item['ord_smpl_nm'] = ord_smpl_nm
            list_ord_smpl_nm.append(f"'{ord_smpl_nm}'")
        list_ord_smpl_nm_str = ', '.join(list_ord_smpl_nm)

        select_query_3 = f''' 
            SELECT ORD_SMPL_NM as ord_smpl_nm
                   , ORD_NO as lims_ord_no
              FROM V_PGS_ORD 
             WHERE ORD_SMPL_NM in ( {list_ord_smpl_nm_str} )
               AND ORD_PRGR_STAT_CD IN ('20', '30', '39', '50')
             ORDER BY FIELD ( ORD_SMPL_NM, {list_ord_smpl_nm_str} )
        '''
        v_pgs_result = queryall('b2b', select_query_3)
        # dict_v_pgs_result = {item['kit_id']: item['lims_ord_no'] for item in v_pgs_result.rows}

        temp_dict = {}
        for item in v_pgs_result.rows:
            ord_smpl_nm = item['ord_smpl_nm']
            lims_ord_no = item['lims_ord_no']
            if ord_smpl_nm not in temp_dict:
                temp_dict[ord_smpl_nm] = []
            temp_dict[ord_smpl_nm].append(lims_ord_no)

        # ord_smpl_nm별로 HP와 HN 시작하는 값을 확인하여 HP 우선으로 결과를 구성
        dict_v_pgs_result = {}
        for ord_smpl_nm, lims_ord_no_list in temp_dict.items():
            if any(item.startswith('HP') for item in lims_ord_no_list):
                dict_v_pgs_result[ord_smpl_nm] = next(item for item in lims_ord_no_list if item.startswith('HP'))
            else:
                dict_v_pgs_result[ord_smpl_nm] = next(item for item in lims_ord_no_list if item.startswith('HN'))

        for item in combined_result:
            if item['ord_smpl_nm'] in dict_v_pgs_result:
                item['lims_ord_no'] = dict_v_pgs_result[item['ord_smpl_nm']]
            else:
                item['lims_ord_no'] = ''

        list_lims_ord_no = [row['lims_ord_no'] for row in combined_result]
        # str_lims_ord_no = ', '.join([f"'{lims_ord_no}'" for lims_ord_no in list_lims_ord_no if lims_ord_no != '']) # WHERE 절 안에 쓸 수 있도록 '', '', ...  의 형태로 조정
        filter_lims_ord_no = [f"'{lims_ord_no}'" for lims_ord_no in list_lims_ord_no if lims_ord_no != '']

        if len(filter_lims_ord_no) != 0:
            str_lims_ord_no = ', '.join(filter_lims_ord_no)
        else:
            str_lims_ord_no = None

        # 3. 2의 결과로 mgs.tb_sale_orders 조회
        #    리스트가 비어 있지 않은 경우만 쿼리 실행
        if str_lims_ord_no:

            query_string = f'''
                SELECT tso.orderCode AS lims_ord_no
                       , tso.kitid AS kit_id
                       , tso.productCode AS mgs_product_code
                       , DATE_FORMAT(tsa.analysis_finish_datetime, '%Y-%m-%d') AS report_date
                  FROM tb_sale_orders tso
                  LEFT JOIN tb_sale_analysis tsa
                        ON tso.kitid = tsa.kitid
                   AND tso.orderCode = tsa.orderCode
                 WHERE 1=1
                   AND tso.orderCode IN ({str_lims_ord_no})
                   AND tso.productCode <> 'ancestry'
            '''

            mgs_result = queryall('mgs', query_string)

            dict_b2b_result = {row['lims_ord_no']: row for row in combined_result}

            # coworker_name 변경
            for key, value in dict_b2b_result.items():
                value.pop('agreement_num')
                value.pop('ord_smpl_nm')
                if value['coworker_name'] in ['microbiome', 'socialbean', 'wadiz']:
                    value['coworker_name'] = 'microbiome'

            dict_mgs_result = defaultdict(list)
            for row in mgs_result.rows:
                dict_mgs_result[row['lims_ord_no']].append(row)

            common_lims_ord_no = set(dict_b2b_result.keys()) & set(dict_mgs_result.keys())

            # 4. 2와 3의 교집합을 구하여 pdf 존재여부 파악
            dict_merge_result = []

            for lims_ord_no in common_lims_ord_no:
                # b2b에서의 해당 lims_ord_no의 row
                b2b_row = dict_b2b_result[lims_ord_no]

                # mgs에서의 해당 lims_ord_no의 모든 row에 대해서
                for mgs_row in dict_mgs_result[lims_ord_no]:
                    merged_dict = b2b_row.copy()
                    merged_dict.update(mgs_row)

                    # report_url을 mgs_product_code를 포함하게 수정
                    merged_dict[
                        'report_url'] = f"https://gentok.macrogen.com/pdf/v1/download?kit_id={merged_dict['kit_id']}&mgs_product_code={merged_dict['mgs_product_code']}&lims_ord_no={merged_dict['lims_ord_no']}"
                    # merged_dict['report_url'] = None

                    # user_collect_date이 None이 아니면 strftime으로 포맷 변경
                    if merged_dict["user_collect_date"] is not None:
                        merged_dict["user_collect_date"] = merged_dict["user_collect_date"].strftime("%Y-%m-%d")

                    dict_merge_result.append(merged_dict)

            # TODO: 1. find_pdf_file로 파일이 있는지 여부를 체크해서 response 하는 것
            # TODO: 2. 또는 download시 참고할 값 DB에 insert

            # dict_merge_result이 비어있지 않으면, 값을 반환
            log_http_request_response(dict_merge_result, HTTPStatus.OK, request_date)

            # check_pdf cache 추가
            insert_check_pdf_cache(pdf_cache_data, json.dumps(dict_merge_result), request_date)
            return jsonify(dict_merge_result), HTTPStatus.OK

        json_msg = {"message": "not found"}
        log_http_request_response(json_msg, HTTPStatus.NOT_FOUND, request_date)
        return jsonify(json_msg), HTTPStatus.NOT_FOUND
    else:
        # dict_merge_result이 비어있지 않으면, 값을 반환
        json_result = json.loads(request_info)
        log_http_request_response(json_result, HTTPStatus.OK, request_date)
        return jsonify(json_result), HTTPStatus.OK


@bp.route('/check', methods=['POST'])
# @request_logging
@authenticate
def bp_post_check():
    """
    1. 입력받은 json에서 ci의 유무 확인

    2. tb_agreement_user에서 di 조건으로 값 조회
       b2borderList_v7에서 ci 조건으로 값 조회 (kit_id는 2가 있으면 2, 아니면 1)

    3. 2의 결과로 mgs.tb_sale_orders 조회

    4. 2와 3의 교집합을 구하여 pdf 존재여부 파악

    5. pdf가 존재한다면 response를 작성
    """

    request_date = datetime.now()  # 요청 시간 기록
    data = request.json
    pdf_cache_data = json.dumps(data)
    request_info = get_check_pdf_cache(pdf_cache_data)

    if request_info == '':
        # 1. 입력받은 json에서 ci의 유무 확인
        def safe_strip(value):
            return value.strip() if value else ""

        ci = safe_strip(data.get('ci'))
        di = safe_strip(data.get('di'))

        coworker_name = data.get('coworker_name', None)
        service = data.get('service', None)
        # user_collect_date = data.get('user_collect_date', None)
        product_code = data.get('product_code', None)
        user_name = data.get('user_name', None)
        gentok_order_code = data.get('gentok_order_code', None)
        kit_id = data.get('kit_id', None)

        if not ci and not di:
            json_msg = {"error": "ci or di is required"}
            log_http_request_response(json_msg, HTTPStatus.BAD_REQUEST, request_date)
            return jsonify(json_msg), HTTPStatus.BAD_REQUEST

        select_query_1 = '''
            SELECT IFNULL(( SELECT DISTINCT IFNULL(kitID_2, kitID_1) FROM vw_b2borderList_all_no_bs WHERE kitID_1 = vau.kitid ), vau.kitid) AS kit_id
                   , vau.platform_order_code AS gentok_order_code
                   , vau.agreement_num
                   , vau.user_name
                   , vau.productCode as product_code
                   , CASE
                         WHEN tcc.coworker = vau.coworker THEN 'gentok'
                         ELSE vau.coworker
                     END AS coworker_name
                   , vau.user_collect_date
                   , vau.omics_type AS service
              FROM vw_agreement_user vau
              LEFT JOIN tb_coworker_content tcc
                     ON vau.coworker = tcc.coworker
                    AND tcc.id = 'is_gentok_sub_coworker' 
                    AND tcc.content = '1' 
                    AND tcc.service = 'genome'
                    AND tcc.a_type = 'common'
             WHERE 1=1
               AND vau.del = '0'
        '''

        params_1 = []

        if ci and di:
            select_query_1 += " AND (vau.user_cert_ci = %s OR vau.user_cert_di = %s)"
            params_1.extend([ci, di])
        elif ci:
            select_query_1 += " AND vau.user_cert_ci = %s"
            params_1.append(ci)
        elif di:
            select_query_1 += " AND vau.user_cert_di = %s"
            params_1.append(di)

        select_query_2 = '''
            SELECT IFNULL(`kitID_2`, `kitID_1`) AS kit_id
                   , NULL AS gentok_order_code
                   , '0' as agreement_num
                   , client_name as user_name
                   , product_code
                   , coworker_name
                   , IFNULL(`lims_collected_date_2`, `lims_collected_date_1`) AS `user_collect_date`
                   , 'genome' as service
              FROM b2borderList_v7
             WHERE 1=1
               AND coworker_clientKey = %s
               AND requestStatus = '04'
               AND del IS NULL
        '''

        params_2 = [ci, ]

        # 파라미터에 따라 query where 조건 변경
        if coworker_name is not None:
            select_query_1 += " AND vau.coworker = %s"
            select_query_2 += " AND coworker_name = %s"
            params_1.append(coworker_name)
            params_2.append(coworker_name)

        if service is not None:
            if service == "genome":
                select_query_1 += " AND vau.omics_type = 'genome'"
            elif service == "biome":
                select_query_1 += " AND vau.omics_type IN ('biome', 'thebiome')"

        if product_code is not None:
            select_query_1 += " AND vau.productCode = %s"
            select_query_2 += " AND product_code = %s"
            params_1.append(product_code)
            params_2.append(product_code)

        if user_name is not None:
            select_query_1 += " AND vau.user_name = %s"
            select_query_2 += " AND client_name = %s"
            params_1.append(user_name)
            params_2.append(user_name)

        if gentok_order_code is not None:
            select_query_1 += " AND vau.platform_order_code = %s"
            params_1.append(gentok_order_code)

        if kit_id is not None:
            select_query_1 += " AND vau.kitid = %s"
            select_query_2 += " AND kitID_1 = %s"
            params_1.append(kit_id)
            params_2.append(kit_id)

        # 2. tb_agreement_user에서 di 조건으로 값 조회
        #    b2borderList_v7에서 ci 조건으로 값 조회 (kit_id는 2가 있으면 2, 아니면 1)

        # TODO: AND tau.service = 'genome' 고쳐야 함.
        # 분석 DB에 없으면 DTC DB에서 조회
        anal_tau_result = queryall('anal', select_query_1, params_1)
        tau_result = queryall('b2b', select_query_1, params_1)
        v7_result = queryall('b2b', select_query_2, params_2)

        # 재채취키트 존재시 재채취 키트번호로 교체
        for anal_order in anal_tau_result.rows:
            for idx, tau_order in enumerate(tau_result.rows):
                if (anal_order['gentok_order_code'] == tau_order['gentok_order_code']
                        and anal_order['kit_id'] != tau_order['kit_id']):
                    tau_result.rows[idx]['kit_id'] = anal_order['kit_id']
                else:
                    pass

        combined_result = tau_result.rows + v7_result.rows

        if len(combined_result) == 0:
            json_msg = {"message": "not found"}
            log_http_request_response(json_msg, HTTPStatus.NOT_FOUND, request_date)
            return jsonify(json_msg), HTTPStatus.NOT_FOUND

        list_ord_smpl_nm = []
        for item in combined_result:
            agreement_num = item['agreement_num']
            if agreement_num == '0':
                ord_smpl_nm = item['kit_id']
            else:
                ord_smpl_nm = f"{item['kit_id']}-{agreement_num}"
            item['ord_smpl_nm'] = ord_smpl_nm
            list_ord_smpl_nm.append(f"'{ord_smpl_nm}'")
        list_ord_smpl_nm_str = ', '.join(list_ord_smpl_nm)

        select_query_3 = f''' 
            SELECT ORD_SMPL_NM as ord_smpl_nm
                   , ORD_NO as lims_ord_no
              FROM V_PGS_ORD 
             WHERE ORD_SMPL_NM in ( {list_ord_smpl_nm_str} )
               AND ORD_PRGR_STAT_CD IN ('20', '30', '39', '50')
             ORDER BY FIELD ( ORD_SMPL_NM, {list_ord_smpl_nm_str} )
        '''
        v_pgs_result = queryall('b2b', select_query_3)
        # dict_v_pgs_result = {item['kit_id']: item['lims_ord_no'] for item in v_pgs_result.rows}

        temp_dict = {}
        for item in v_pgs_result.rows:
            ord_smpl_nm = item['ord_smpl_nm']
            lims_ord_no = item['lims_ord_no']
            if ord_smpl_nm not in temp_dict:
                temp_dict[ord_smpl_nm] = []
            temp_dict[ord_smpl_nm].append(lims_ord_no)

        # ord_smpl_nm별로 HP와 HN 시작하는 값을 확인하여 HP 우선으로 결과를 구성
        dict_v_pgs_result = {}
        for ord_smpl_nm, lims_ord_no_list in temp_dict.items():
            if any(item.startswith('HP') for item in lims_ord_no_list):
                dict_v_pgs_result[ord_smpl_nm] = next(item for item in lims_ord_no_list if item.startswith('HP'))
            else:
                dict_v_pgs_result[ord_smpl_nm] = next(item for item in lims_ord_no_list if item.startswith('HN'))

        for item in combined_result:
            if item['ord_smpl_nm'] in dict_v_pgs_result:
                item['lims_ord_no'] = dict_v_pgs_result[item['ord_smpl_nm']]
            else:
                item['lims_ord_no'] = ''

        list_lims_ord_no = [row['lims_ord_no'] for row in combined_result]
        # str_lims_ord_no = ', '.join([f"'{lims_ord_no}'" for lims_ord_no in list_lims_ord_no if lims_ord_no != '']) # WHERE 절 안에 쓸 수 있도록 '', '', ...  의 형태로 조정
        filter_lims_ord_no = [f"'{lims_ord_no}'" for lims_ord_no in list_lims_ord_no if lims_ord_no != '']

        if len(filter_lims_ord_no) != 0:
            str_lims_ord_no = ', '.join(filter_lims_ord_no)
        else:
            str_lims_ord_no = None

        # 3. 2의 결과로 mgs.tb_sale_orders 조회
        #    리스트가 비어 있지 않은 경우만 쿼리 실행
        if str_lims_ord_no:

            query_string = f'''
                SELECT tso.orderCode AS lims_ord_no
                       , tso.kitid AS kit_id
                       , tso.productCode AS mgs_product_code
                       , DATE_FORMAT(tsa.analysis_finish_datetime, '%Y-%m-%d') AS report_date
                  FROM tb_sale_orders tso
                  LEFT JOIN tb_sale_analysis tsa
                        ON tso.kitid = tsa.kitid
                   AND tso.orderCode = tsa.orderCode
                 WHERE 1=1
                   AND tso.orderCode IN ({str_lims_ord_no})
                   AND tso.productCode <> 'ancestry'
            '''

            mgs_result = queryall('mgs', query_string)

            dict_b2b_result = {row['lims_ord_no']: row for row in combined_result}

            # coworker_name 변경
            for key, value in dict_b2b_result.items():
                value.pop('agreement_num')
                value.pop('ord_smpl_nm')
                if value['coworker_name'] in ['microbiome', 'socialbean', 'wadiz']:
                    value['coworker_name'] = 'microbiome'

            dict_mgs_result = defaultdict(list)
            for row in mgs_result.rows:
                dict_mgs_result[row['lims_ord_no']].append(row)

            common_lims_ord_no = set(dict_b2b_result.keys()) & set(dict_mgs_result.keys())

            # 4. 2와 3의 교집합을 구하여 pdf 존재여부 파악
            dict_merge_result = []
            serialize_dict_merge_result = {}

            for lims_ord_no in common_lims_ord_no:
                # b2b에서의 해당 lims_ord_no의 row
                b2b_row = dict_b2b_result[lims_ord_no]

                # mgs에서의 해당 lims_ord_no의 모든 row에 대해서
                for mgs_row in dict_mgs_result[lims_ord_no]:
                    merged_dict = b2b_row.copy()
                    merged_dict.update(mgs_row)

                    # report_url을 mgs_product_code를 포함하게 수정
                    merged_dict[
                        'report_url'] = f"https://gentok.macrogen.com/pdf/v1/download?kit_id={merged_dict['kit_id']}&mgs_product_code={merged_dict['mgs_product_code']}&lims_ord_no={merged_dict['lims_ord_no']}"
                    # merged_dict['report_url'] = None

                    # user_collect_date이 None이 아니면 strftime으로 포맷 변경
                    if isinstance(merged_dict["user_collect_date"], datetime):
                        merged_dict["user_collect_date"] = merged_dict["user_collect_date"].strftime("%Y-%m-%d")

                    dict_merge_result.append(merged_dict)

            serialize_dict_merge_result = serialize_for_json(dict_merge_result)

            # TODO: 1. find_pdf_file로 파일이 있는지 여부를 체크해서 response 하는 것
            # TODO: 2. 또는 download시 참고할 값 DB에 insert

            # serialize_dict_merge_result이 비어있지 않으면, 값을 반환
            if serialize_dict_merge_result:
                log_http_request_response(serialize_dict_merge_result, HTTPStatus.OK, request_date)

            # check_pdf cache 추가
            insert_check_pdf_cache(pdf_cache_data, json.dumps(serialize_dict_merge_result), request_date)
            return jsonify(serialize_dict_merge_result), HTTPStatus.OK

        json_msg = {"message": "not found"}
        log_http_request_response(json_msg, HTTPStatus.NOT_FOUND, request_date)
        return jsonify(json_msg), HTTPStatus.NOT_FOUND
    else:
        # dict_merge_result이 비어있지 않으면, 값을 반환
        json_result = json.loads(request_info)
        log_http_request_response(json_result, HTTPStatus.OK, request_date)
        return jsonify(json_result), HTTPStatus.OK


@bp.route('/check_kitid', methods=['POST'])
# @request_logging
@authenticate
def bp_post_check_kitid():
    """
    1. 입력받은 json에서 kitid의 유무 확인

    2. mgs.tb_sale_orders 조회

    3. pdf 존재여부 파악

    4. pdf가 존재한다면 response를 작성
    """

    request_date = datetime.now()  # 요청 시간 기록

    # 1. 입력받은 json에서 kitid의 유무 확인
    data = request.json

    def safe_strip(value):
        return value.strip() if value else ""

    kitid = safe_strip(data.get('kitid'))

    if not kitid:
        json_msg = {"error": "kitid is required"}
        log_http_request_response(json_msg, HTTPStatus.BAD_REQUEST, request_date)
        return jsonify(json_msg), HTTPStatus.BAD_REQUEST

    select_query_1 = f''' 
        SELECT ORD_SMPL_NM as ord_smpl_nm
                , ORD_NO as lims_ord_no
            FROM V_PGS_ORD 
            WHERE ORD_SMPL_NM = %s
            AND ORD_PRGR_STAT_CD IN ('20', '30', '39', '50')
    '''
    v_pgs_result = queryone('b2b', select_query_1, [kitid, ])

    if v_pgs_result.error:
        json_msg = {"error": "b2b db error"}
        log_http_request_response(json_msg, HTTPStatus.INTERNAL_SERVER_ERROR, request_date)
        return jsonify(json_msg), HTTPStatus.INTERNAL_SERVER_ERROR

    if not v_pgs_result.rows:
        json_msg = {"message": "not found"}
        log_http_request_response(json_msg, HTTPStatus.NOT_FOUND, request_date)
        return jsonify(json_msg), HTTPStatus.NOT_FOUND

    v_lims_ord_no = v_pgs_result.rows['lims_ord_no']

    # 2. mgs.tb_sale_orders 조회
    #    리스트가 비어 있지 않은 경우만 쿼리 실행
    if v_lims_ord_no:
        query_string = f'''
            SELECT tso.orderCode AS lims_ord_no
                    , tso.kitid AS kit_id
                    , tso.productCode AS mgs_product_code
                    , DATE_FORMAT(tsa.analysis_finish_datetime, '%Y-%m-%d') AS report_date
                FROM tb_sale_orders tso
                LEFT JOIN tb_sale_analysis tsa
                    ON tso.kitid = tsa.kitid
                AND tso.orderCode = tsa.orderCode
                WHERE 1=1
                AND tso.orderCode = %s
                AND tso.kitid = %s
                AND tso.productCode <> 'ancestry'
        '''

        mgs_result = queryall('mgs', query_string, [v_lims_ord_no, kitid])

        if mgs_result.error:
            json_msg = {"error": "mgs db error"}
            log_http_request_response(json_msg, HTTPStatus.INTERNAL_SERVER_ERROR, request_date)
            return jsonify(json_msg), HTTPStatus.INTERNAL_SERVER_ERROR

        if not mgs_result.rows:
            json_msg = {"message": "not found"}
            log_http_request_response(json_msg, HTTPStatus.NOT_FOUND, request_date)
            return jsonify(json_msg), HTTPStatus.NOT_FOUND

        dict_b2b_result = {v_lims_ord_no: v_pgs_result.rows}

        dict_mgs_result = defaultdict(list)
        for row in mgs_result.rows:
            dict_mgs_result[row['lims_ord_no']].append(row)

        common_lims_ord_no = set(dict_b2b_result.keys()) & set(dict_mgs_result.keys())

        # 4. 2와 3의 교집합을 구하여 pdf 존재여부 파악
        dict_merge_result = []
        serialize_dict_merge_result = {}

        for lims_ord_no in common_lims_ord_no:
            # b2b에서의 해당 lims_ord_no의 row
            b2b_row = dict_b2b_result[lims_ord_no]

            # mgs에서의 해당 lims_ord_no의 모든 row에 대해서
            for mgs_row in dict_mgs_result[lims_ord_no]:
                merged_dict = b2b_row.copy()
                merged_dict.update(mgs_row)

                # report_url을 mgs_product_code를 포함하게 수정
                merged_dict[
                    'report_url'] = f"https://gentok.macrogen.com/pdf/v1/download?kit_id={merged_dict['kit_id']}&mgs_product_code={merged_dict['mgs_product_code']}&lims_ord_no={merged_dict['lims_ord_no']}"
                # merged_dict['report_url'] = None

                dict_merge_result.append(merged_dict)
                serialize_dict_merge_result = serialize_for_json(dict_merge_result)

        # TODO: 1. find_pdf_file로 파일이 있는지 여부를 체크해서 response 하는 것
        # TODO: 2. 또는 download시 참고할 값 DB에 insert

        # serialize_dict_merge_result이 비어있지 않으면, 값을 반환
        if serialize_dict_merge_result:
            log_http_request_response(serialize_dict_merge_result, HTTPStatus.OK, request_date)

        # check_pdf cache 추가
        # insert_check_pdf_cache(pdf_cache_data, json.dumps(serialize_dict_merge_result), request_date)
        return jsonify(serialize_dict_merge_result), HTTPStatus.OK

    json_msg = {"message": "not found"}
    log_http_request_response(json_msg, HTTPStatus.NOT_FOUND, request_date)
    return jsonify(json_msg), HTTPStatus.NOT_FOUND


# else:
#     # dict_merge_result이 비어있지 않으면, 값을 반환
#     json_result = json.loads(request_info)
#     log_http_request_response(json_result, HTTPStatus.OK, request_date)
#     return jsonify(json_result), HTTPStatus.OK


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    raise TypeError(f"Type {type(obj)} not serializable")


def find_pdf_file(kit_id, lims_ord_no):
    folder_path = '/data/mygenomestory_web_reports'  # 파일을 찾을 폴더의 경로
    for file in os.scandir(folder_path):
        if file.is_file() and file.name.endswith('.pdf'):
            if kit_id in file.name and lims_ord_no in file.name:
                return os.path.join(folder_path, file.name)
    return None


@bp.route('/download_old', methods=['GET'])
# @request_logging
@authenticate
def bp_get_download_old():
    request_date = datetime.now()  # 요청 시간 기록

    kit_id = request.args.get('kit_id')
    mgs_product_code = request.args.get('mgs_product_code')
    lims_ord_no = request.args.get('lims_ord_no')

    status_code = HTTPStatus.OK

    try:
        query_string = '''
            SELECT CONCAT(kitid, '_', productCode, '_', orderCode, '.pdf') AS file_name
              FROM tb_sale_orders
             WHERE 1=1
               AND kitid = %s
               AND productCode = %s
               AND orderCode = %s
               AND productCode <> 'ancestry'
               AND productCode IS NOT NULL
        '''
        q_result = queryone('mgs', query_string, (kit_id, mgs_product_code, lims_ord_no))

        if q_result.error is not None:
            payload = str(q_result.error)
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            return payload, status_code

        file_name = q_result.rows['file_name']
        file_path = f'/data/mygenomestory_web_reports/{file_name}'

        payload = file_path
        status_code = HTTPStatus.OK
        return send_file(file_path, as_attachment=True, attachment_filename=file_name)

    except FileNotFoundError as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.NOT_FOUND
        return jsonify(payload), status_code

    except Exception as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        return jsonify(payload), status_code

    finally:
        log_http_request_response(payload, status_code, request_date)


@bp.route('/download', methods=['GET'])
@authenticate
def bp_get_download():
    request_date = datetime.now()
    payload = None

    kit_id = request.args.get('kit_id')
    mgs_product_code = request.args.get('mgs_product_code')
    lims_ord_no = request.args.get('lims_ord_no')

    status_code = HTTPStatus.OK

    try:
        query_string = '''
            SELECT CONCAT(kitid, '_', productCode, '_', orderCode, '.pdf') AS file_name
              FROM tb_sale_orders
             WHERE 1=1
               AND kitid = %s
               AND productCode = %s
               AND orderCode = %s
               AND productCode <> 'ancestry'
               AND productCode IS NOT NULL
        '''
        q_result = queryone('mgs', query_string, (kit_id, mgs_product_code, lims_ord_no))

        if q_result.error is not None:
            payload = str(q_result.error)
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            return payload, status_code

        file_name = q_result.rows['file_name']
        response = Response()
        response.headers['X-Accel-Redirect'] = f'/internal-reports/{file_name}'
        response.headers['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response.headers['Content-Type'] = 'application/pdf'
        return response

    except FileNotFoundError as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.NOT_FOUND
        return jsonify(payload), status_code

    except Exception as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        return jsonify(payload), status_code

    finally:
        log_http_request_response(payload, status_code, request_date)


@bp.route('/download_etc', methods=['GET'])
# @request_logging
@authenticate
def bp_get_download_etc():
    # 예시: 99244352_ms50_Healthycheck12_HP00443176.pdf

    request_date = datetime.now()  # 요청 시간 기록

    kit_id = request.args.get('kit_id')
    mgs_product_code = request.args.get('mgs_product_code')
    lims_ord_no = request.args.get('lims_ord_no')

    status_code = HTTPStatus.OK

    try:
        # query_string = '''
        #     SELECT CONCAT(kitid, '_', productCode, '_', orderCode, '.pdf') AS file_name
        #       FROM tb_sale_orders
        #      WHERE 1=1
        #        AND kitid = %s
        #        AND productCode = %s
        #        AND orderCode = %s
        #        AND productCode <> 'ancestry'
        #        AND productCode IS NOT NULL
        # '''
        # q_result = queryone('mgs', query_string, (kit_id, mgs_product_code, lims_ord_no))

        # if q_result.error is not None:
        #     payload = str(q_result.error)
        #     status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        #     return payload, status_code

        # file_name = q_result.rows['file_name']
        file_name = f'{kit_id}_{mgs_product_code}_{lims_ord_no}.pdf'
        file_path = f'/data/mygenomestory_web_reports_etc/{file_name}'

        payload = file_path
        status_code = HTTPStatus.OK
        return send_file(file_path, as_attachment=True, attachment_filename=file_name)

    except FileNotFoundError as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.NOT_FOUND
        return jsonify(payload), status_code

    except Exception as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        return jsonify(payload), status_code

    finally:
        log_http_request_response(payload, status_code, request_date)


@bp.route('/agreement/download', methods=['POST'])
# @request_logging
@authenticate
def bp_get_agreement_download():
    request_date = datetime.now()  # 요청 시간 기록

    data = request.json

    kit_id = data.get('kit_id')
    user_cert_di = data.get('user_cert_di')
    agreement_type = data.get('agreement_type')
    agreement_no = data.get('agreement_no')

    status_code = HTTPStatus.OK

    try:
        query_string = '''
            SELECT coworker
                ,omics_type
                ,user_cert_req_number
            FROM vw_agreement_user
            WHERE user_cert_di = %s
                AND kitid = %s
                AND agreement_num = %s
                AND del = 0
        '''
        q_result = queryone('b2b', query_string, (user_cert_di, kit_id, agreement_no))

        if q_result.error is not None:
            payload = str(q_result.error)
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            return payload, status_code

        coworker = q_result.rows['coworker']
        omics_type = q_result.rows['omics_type']
        user_cert_req_number = q_result.rows['user_cert_req_number']

        if omics_type == 'genome':
            agreement_type_map = {
                "agree": "for_customer_dl_agree_genome",
                "request": "for_customer_dl_request_genome",
                "material": "for_customer_dl_human_material_genome",
                "donate": "for_customer_dl_human_material_donate_genome",
            }

            agreement_name_map = {
                "agree": "dl_agree",
                "request": "dl_request",
                "material": "dl_human_material",
                "donate": "dl_human_material_donate",
            }

            file_name = f'{kit_id}_{user_cert_req_number}_{agreement_name_map[agreement_type]}.pdf'

            file_path = f'/data/agreement_pdf/{agreement_type_map[agreement_type]}/{coworker}/{file_name}'
        else:
            file_name = f'{kit_id}_{user_cert_req_number}_agreement.pdf'
            file_path = f'/data/agreement_pdf/{omics_type}/{coworker}/{file_name}'

        payload = file_path
        status_code = HTTPStatus.OK
        return send_file(file_path, as_attachment=True, attachment_filename=file_name)

    except FileNotFoundError as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.NOT_FOUND
        return jsonify(payload), status_code

    except Exception as e:
        payload = {"error": str(e)}
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        return jsonify(payload), status_code

    finally:
        log_http_request_response(payload, status_code, request_date)


@bp.route('/calendar', methods=['GET'])
# @request_logging
@authenticate
def bp_get_calendar():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    tat_day = request.args.get('tat_day')

    start_datetime = datetime.strptime(str(start_date), "%Y%m%d")

    # start_date <-> end_date 간 working day 계산
    if end_date:
        day_count = 0
        end_datetime = datetime.strptime(str(end_date), "%Y%m%d")

        for _date in range((end_datetime - start_datetime).days + 1):
            if (start_datetime + timedelta(days=_date)).weekday() < 5:
                day_count += 1

        day_count = day_count - get_holiday_count_include_start_date(start_date, end_date)

        return jsonify({"status": "success", "working_day": day_count}), HTTPStatus.OK
    elif tat_day:
        end_date = add_holiday_calc(start_datetime, start_datetime + timedelta(days=int(tat_day))).strftime(
            "%Y/%m/%d %H:%M:%S")

        return jsonify({"status": "success", "end_date": end_date}), HTTPStatus.OK
    else:
        return jsonify({"status": "error",
                        "message": "must have 'end_date' or 'working_day' key"}), HTTPStatus.INTERNAL_SERVER_ERROR


@bp.route('/agreement/<kit_id>/di', methods=['GET'])
# @request_logging
@authenticate
def bp_get_agreement_di(kit_id):
    query_string = """
        SELECT user_cert_di
        FROM tb_agreement_user
        WHERE kitid = %s
            AND del =0
    """
    q_result = queryone('b2b', query_string, (kit_id,))

    if q_result.error is not None:
        return jsonify({"status": "fail", "error": str(q_result.error)}), HTTPStatus.INTERNAL_SERVER_ERROR
    else:
        return jsonify({"status": "success", "di": q_result.rows["user_cert_di"]}), HTTPStatus.OK


@bp.route('/agreement/<kit_id>/ci', methods=['GET'])
# @request_logging
@authenticate
def bp_get_agreement_ci(kit_id):
    query_string = """
        SELECT coworker_clientKey
        FROM tb_agreement_user_v7 
        WHERE kitid = %s
            AND del =0
    """
    q_result = queryone('b2b', query_string, (kit_id,))

    if q_result.error is not None:
        return jsonify({"status": "fail", "error": str(q_result.error)}), HTTPStatus.INTERNAL_SERVER_ERROR
    else:
        return jsonify({"status": "success", "ci": q_result.rows["coworker_clientKey"]}), HTTPStatus.OK
