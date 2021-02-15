import logging
from typing import List

from botoy import FriendMsg, GroupMsg
from botoy.refine import refine_pic_friend_msg, refine_voice_friend_msg, refine_pic_group_msg, refine_voice_group_msg
from ehforwarderbot import Message

from efb_qq_plugin_iot.MsgDecorator import efb_text_simple_wrapper, efb_image_wrapper, efb_unsupported_wrapper
from efb_qq_plugin_iot.Utils import download_file

logger = logging.getLogger(__name__)


class IOTMsgProcessor:
    @staticmethod
    def iot_TextMsg_friend(ctx: FriendMsg) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_PhoneMsg_friend(ctx: FriendMsg) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_AtMsg_friend(ctx: FriendMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_BigFaceMsg_friend(ctx: FriendMsg) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_PicMsg_friend(ctx: FriendMsg) -> List[Message]:
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
    def iot_VoiceMsg_friend(ctx: FriendMsg) -> List[Message]:
        refine_voices = refine_voice_friend_msg(ctx)
        if refine_voices:
            try:
                f = download_file(refine_voices.VoiceUrl)
            except Exception as e:
                logger.warning(f"Failed to download the voice! {e}")
            else:
                pass  # fixme
        pass

    @staticmethod
    def iot_FriendFileMsg_friend(ctx: FriendMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_JsonMsg_friend(ctx: FriendMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_XmlMsg_friend(ctx: FriendMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_ReplayMsg_friend(ctx: FriendMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_TextMsg_group(ctx: GroupMsg) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_AtMsg_group(ctx: GroupMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_BigFaceMsg_group(ctx: GroupMsg) -> List[Message]:
        content = ctx.Content if ctx.Content else "[Content missing]"
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    def iot_PicMsg_group(ctx: GroupMsg) -> List[Message]:
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
    def iot_VoiceMsg_group(ctx: GroupMsg) -> List[Message]:
        refine_voices = refine_voice_group_msg(ctx)
        if refine_voices:
            try:
                f = download_file(refine_voices.VoiceUrl)
            except Exception as e:
                logger.warning(f"Failed to download the voice! {e}")
            else:
                pass  # fixme
        pass

    @staticmethod
    def iot_FriendFileMsg_group(ctx: GroupMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_JsonMsg_group(ctx: GroupMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_XmlMsg_group(ctx: GroupMsg) -> List[Message]:
        pass

    @staticmethod
    def iot_ReplayMsg_group(ctx: GroupMsg) -> List[Message]:
        pass

    def __getattr__(self, name):
        if not hasattr(self, name):
            content = f"Unsupported Message Type: {name}"
            return [efb_unsupported_wrapper(content)]

        def wrapper(*args, **kwargs):
            func = getattr(self, name)
            func(*args, **kwargs)
        return wrapper
