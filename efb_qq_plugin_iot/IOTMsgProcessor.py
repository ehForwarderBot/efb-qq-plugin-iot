import json
import logging
import tempfile
from contextlib import suppress
from json.decoder import JSONDecodeError
from typing import List

import pydub as pydub
from botoy import FriendMsg, GroupMsg
from botoy.refine import refine_pic_friend_msg, refine_voice_friend_msg, refine_pic_group_msg, refine_voice_group_msg
from botoy.refine._friend_msg import refine_reply_friend_msg, refine_video_friend_msg, refine_file_friend_msg
from botoy.refine._group_msg import refine_reply_group_msg, refine_at_group_msg, refine_file_group_msg, \
    refine_video_group_msg
from ehforwarderbot import Message, Chat

from efb_qq_plugin_iot.IOTFactory import IOTFactory
from efb_qq_plugin_iot.MsgDecorator import efb_text_simple_wrapper, efb_image_wrapper, efb_unsupported_wrapper, \
    efb_voice_wrapper, efb_video_wrapper, efb_file_wrapper
from efb_qq_plugin_iot.Utils import download_file

logger = logging.getLogger(__name__)

try:
    import Silkv3

    VOICE_SUPPORTED = True
except ImportError:
    VOICE_SUPPORTED = False


class IOTMsgProcessor:
    def __init__(self, uin: int):
        self.uin = uin

    @staticmethod
    def iot_TextMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_PhoneMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_AtMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        pass

    @staticmethod
    def iot_BigFaceMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_PicMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        messages = []
        refine_pics = refine_pic_friend_msg(ctx)
        if refine_pics:
            for pics in refine_pics.FriendPic:
                try:
                    f = download_file(pics.Url)
                except Exception as e:
                    logger.warning(f"Failed to download the image! {e}")
                    continue
                else:
                    messages.append(efb_image_wrapper(f))
            if refine_pics.Content:
                messages.append(efb_text_simple_wrapper(refine_pics.Content))
        else:
            messages.append(efb_text_simple_wrapper("Received invalid message format(image)! Dumping content\n"
                                                    f"{ctx}. Please report that to the developer."))
        return messages

    @staticmethod
    def iot_VoiceMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        if not VOICE_SUPPORTED:
            content = "[Voice Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]
        refine_voices = refine_voice_friend_msg(ctx)
        if refine_voices:
            try:
                input_file = download_file(refine_voices.VoiceUrl)
            except Exception as e:
                logger.warning(f"Failed to download the voice! {e}")
                content = "[Voice Message, Please check it on your phone]"
                return [efb_unsupported_wrapper(content)]
            else:
                output_file = tempfile.NamedTemporaryFile()
                if not Silkv3.decode(input_file.name, output_file.name):
                    content = "[Voice Message, Please check it on your phone]"
                    return [efb_unsupported_wrapper(content)]
                pydub.AudioSegment.from_raw(file=output_file, sample_width=2, frame_rate=24000, channels=1) \
                    .export(output_file, format="ogg", codec="libopus",
                            parameters=['-vbr', 'on'])
                return [efb_voice_wrapper(output_file)]
        else:
            content = "[Voice Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_VideoMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        refine_video = refine_video_friend_msg(ctx)
        if refine_video:
            video_raw_url = refine_video.VideoUrl
            video_md5 = refine_video.VideoMd5
            try:
                video_info = IOTFactory.action.getVideoURL(group=0,
                                                           videoURL=video_raw_url,
                                                           videoMD5=video_md5)
                video_file = download_file(video_info.get('VideoUrl', ''))
            except Exception as e:
                logger.warning(f"Failed to download the video! {e}")
                content = "[Video Message, Please check it on your phone]"
                return [efb_unsupported_wrapper(content)]
            else:
                return [efb_video_wrapper(video_file)]
        else:
            content = "[Video Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_FriendFileMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        refine_file = refine_file_friend_msg(ctx)
        if refine_file:
            file_id = refine_file.FileID
            file_size = refine_file.FileSize
            file_name = refine_file.FileName
            if file_size > 50 * 1024 * 1024:  # 50M
                content = "[File too large, Please check it on your phone]\n" \
                          f"File name: {file_name}\n" \
                          f"File size: {file_size}\n" \
                          f"File id: {file_id}"
                return [efb_unsupported_wrapper(content)]
            try:
                file_info = IOTFactory.action.getFriendFileURL(file_id)
                actual_file = download_file(file_info.get('Url', ''))
            except Exception as e:
                logger.warning(f"Failed to download the file! {e}")
                content = "[File message, Please check it on your phone]"
                return [efb_unsupported_wrapper(content)]
            else:
                return [efb_file_wrapper(actual_file, file_name)]
        else:
            content = "[File Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_JsonMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        with suppress(Exception):
            ctx.Content = json.loads(ctx.Content)
        content = str(ctx.Content)
        return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_XmlMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        with suppress(Exception):
            ctx.Content = json.loads(ctx.Content)
        content = str(ctx.Content)
        return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_ReplyMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        return IOTMsgProcessor.iot_ReplayMsg_friend(ctx)

    @staticmethod
    def iot_ReplayMsg_friend(ctx: FriendMsg, chat: Chat) -> List[Message]:
        refine_reply = refine_reply_friend_msg(ctx)
        if refine_reply:
            quote_text = f"「{refine_reply.SrcContent}」\n\n{refine_reply.Content}"
        else:
            quote_text = "[Missing message]"
        return [efb_text_simple_wrapper(quote_text)]

    @staticmethod
    def iot_TextMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    def iot_AtMsg_group(self, ctx: GroupMsg, chat: Chat) -> List[Message]:
        refine_at = refine_at_group_msg(ctx)
        quote_text = ""
        if refine_at:
            if refine_at.SrcContent:
                quote_text = f"「{refine_at.SrcContent}」\n\n"
            quote_text += refine_at.Content
        else:
            quote_text = "[Missing message]"
        at_list = {}
        if self.uin in refine_at.AtUserID:  # Being mentioned
            begin_index = len(quote_text)
            quote_text += ' @me'
            end_index = len(quote_text)
            at_list[(begin_index, end_index)] = chat.self
        return [efb_text_simple_wrapper(quote_text, at_list)]

    @staticmethod
    def iot_BigFaceMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_PicMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        messages = []
        refine_pics = refine_pic_group_msg(ctx)
        if refine_pics:
            for pics in refine_pics.GroupPic:
                try:
                    f = download_file(pics.Url)
                except Exception as e:
                    logger.warning(f"Failed to download the image! {e}")
                    continue
                else:
                    messages.append(efb_image_wrapper(f))
            if refine_pics.Content:
                messages.append(efb_text_simple_wrapper(refine_pics.Content))
        else:
            messages.append(efb_text_simple_wrapper("Received invalid message format(image)! Dumping content\n"
                                                    f"{ctx}. Please report that to the developer."))
        return messages

    @staticmethod
    def iot_VideoMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        refine_video = refine_video_group_msg(ctx)
        if refine_video:
            video_raw_url = refine_video.VideoUrl
            video_md5 = refine_video.VideoMd5
            try:
                video_info = IOTFactory.action.getVideoURL(group=ctx.FromGroupId,
                                                           videoURL=video_raw_url,
                                                           videoMD5=video_md5)
                video_file = download_file(video_info.get('VideoUrl', ''))
            except Exception as e:
                logger.warning(f"Failed to download the video! {e}")
                content = "[Video Message, Please check it on your phone]"
                return [efb_unsupported_wrapper(content)]
            else:
                return [efb_video_wrapper(video_file)]
        else:
            content = "[Video Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_VoiceMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        if not VOICE_SUPPORTED:
            content = "[Voice Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]
        refine_voices = refine_voice_group_msg(ctx)
        if refine_voices:
            try:
                input_file = download_file(refine_voices.VoiceUrl)
            except Exception as e:
                logger.warning(f"Failed to download the voice! {e}")
                content = "[Voice Message, Please check it on your phone]"
                return [efb_unsupported_wrapper(content)]
            else:
                output_file = tempfile.NamedTemporaryFile()
                if not Silkv3.decode(input_file.name, output_file.name):
                    content = "[Voice Message, Please check it on your phone]"
                    return [efb_unsupported_wrapper(content)]
                pydub.AudioSegment.from_raw(file=output_file, sample_width=2, frame_rate=24000, channels=1) \
                    .export(output_file, format="ogg", codec="libopus",
                            parameters=['-vbr', 'on'])
                return [efb_voice_wrapper(output_file)]
        else:
            content = "[Voice Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_GroupFileMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        refine_file = refine_file_group_msg(ctx)
        if refine_file:
            file_id = refine_file.FileID
            file_size = refine_file.FileSize
            file_name = refine_file.FileName
            if file_size > 50 * 1024 * 1024:  # 50M
                content = "[File too large, Please check it on your phone]\n" \
                          f"File name: {file_name}\n" \
                          f"File size: {file_size}\n" \
                          f"File id: {file_id}"
                return [efb_unsupported_wrapper(content)]
            try:
                file_info = IOTFactory.action.getGroupFileURL(ctx.FromGroupId, file_id)
                actual_file = download_file(file_info.get('Url', ''))
            except Exception as e:
                logger.warning(f"Failed to download the file! {e}")
                content = "[File message, Please check it on your phone]"
                return [efb_unsupported_wrapper(content)]
            else:
                return [efb_file_wrapper(actual_file, file_name)]
        else:
            content = "[File Message, Please check it on your phone]"
            return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_JsonMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        with suppress(Exception):
            ctx.Content = json.loads(ctx.Content)
        content = str(ctx.Content)
        return [efb_unsupported_wrapper(content)]

    @staticmethod
    def iot_XmlMsg_group(ctx: GroupMsg, chat: Chat) -> List[Message]:
        with suppress(Exception):
            ctx.Content = json.loads(ctx.Content)
        content = str(ctx.Content)
        return [efb_unsupported_wrapper(content)]

    def iot_ReplyMsg_group(self, ctx: GroupMsg, chat: Chat) -> List[Message]:
        return self.iot_ReplayMsg_group(ctx, chat)

    def iot_ReplayMsg_group(self, ctx: GroupMsg, chat: Chat) -> List[Message]:
        refine_reply = refine_reply_group_msg(ctx)
        if refine_reply:
            quote_text = f"「{refine_reply.SrcContent}」\n\n{refine_reply.Content}"
        else:
            quote_text = "[Missing message]"
        at_list = {}
        if self.uin in refine_reply.AtUserID:  # Being mentioned
            # todo Use msg.target for reply message
            begin_index = len(quote_text)
            quote_text += ' @me'
            end_index = len(quote_text)
            at_list[(begin_index, end_index)] = chat.self
        return [efb_text_simple_wrapper(quote_text, at_list)]

    def __getattr__(self, name):
        def fallback(*args, **kwargs):
            content = f"Unsupported Message Type: {name}"
            return [efb_unsupported_wrapper(content)]
        return fallback
