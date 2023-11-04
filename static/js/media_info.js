import $ from '/libs/jquery.js';
import { decode } from './prod/codec-string.js';

function setCodecDescription() {
    const codecDescription = decode($('.codec-string').text());
    $('.codec-description').html(codecDescription);
}

setCodecDescription();
