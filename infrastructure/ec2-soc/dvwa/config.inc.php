<?php
// Original path: /var/www/dvwa/config/config.inc.php
//
// DVWA settings. The password below is a PLACEHOLDER — the real value exists
// only on the host (created during DVWA setup) and must never be committed.
// This snapshot records which keys are set, not their secrets.

$DBMS = 'MySQL';

$_DVWA = array();
$_DVWA['db_server']   = '127.0.0.1';
$_DVWA['db_database'] = 'dvwa';
$_DVWA['db_user']     = 'dvwa';
$_DVWA['db_password'] = 'CHANGEME_placeholder';
$_DVWA['db_port']     = '3306';

// DVWA ships two ways to set this; modern releases use the value directly.
$_DVWA['default_security_level'] = 'low';

$_DVWA['recaptcha_public_key']  = '';
$_DVWA['recaptcha_private_key'] = '';

// DVWA's default credentials (admin / password) are deliberately left in
// place: the web-login brute-force rule targets the DVWA login form.
