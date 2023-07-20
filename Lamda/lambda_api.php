<?php
$user_real_id = USER_ID;
$Token = TOKEN;
$key = KEY; //salt key
$send_data = '?selectLang='.$userLang.'&gToken='.encrypt($Token,$key)."&realID=".$user_real_id;
$url = 'AWS Lambda URL'.$send_data;

//aws lambda 통신
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_HTTPHEADER, array('Content-Type: application/json'));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'GET');
curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, 0);
$response  = curl_exec($ch);

curl_close($ch);

$res = json_decode($response);
$_SESSION['gToken'] = $res->gToken;

//전송 LOG INSERT
$query_array = array(
    'type'=>'request_to_lambda',
    'user_real_id'=>$user_real_id,
    'send_data'=>$send_data,
    'response'=>$response,
);
$insert_query = "INSERT INTO LOG_TABLE SET ".change_query_string($query_array);
$response = mysql_query($insert_query, $con);

switch($res->isSuc) {
    case "Y" : //선착순 통과
        echo 'URL'.$userLang;
        break;
    case "N" : //선착순 실패
        echo 'URL'.$userLang;
        break;
    default :
        echo 'URL'&ma=MS81A9';
}

?>
