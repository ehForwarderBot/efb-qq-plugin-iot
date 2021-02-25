# coding: utf-8
import base64
import hashlib
import logging
import tempfile
import uuid
from typing import Collection, BinaryIO, Dict, Any, List, Union, IO
import threading

import pydub
from cachetools import TTLCache
from efb_qq_slave import BaseClient
from ehforwarderbot import Chat, Message, Status, coordinator, MsgType
from ehforwarderbot.channel import SlaveChannel
from ehforwarderbot.types import ChatID

from botoy import Botoy, GroupMsg, FriendMsg, EventMsg, Action

from efb_qq_plugin_iot.IOTConfig import IOTConfig
from efb_qq_plugin_iot.IOTFactory import IOTFactory
from efb_qq_plugin_iot.IOTMsgProcessor import IOTMsgProcessor
from efb_qq_plugin_iot.ChatMgr import ChatMgr
from efb_qq_plugin_iot.CustomTypes import IOTGroup, EFBGroupChat, EFBPrivateChat, IOTGroupMember, \
    EFBGroupMember
from efb_qq_plugin_iot.Utils import download_user_avatar, download_group_avatar, iot_at_user, process_quote_text
try:
    import Silkv3
    VOICE_SUPPORTED = True
except ImportError:
    VOICE_SUPPORTED = False


class iot(BaseClient):
    client_name: str = "IOTbot Client"
    client_id: str = "iot"
    client_config: Dict[str, Any]
    bot: Botoy
    action: Action
    channel: SlaveChannel
    logger: logging.Logger = logging.getLogger(__name__)

    info_list = TTLCache(maxsize=2, ttl=600)

    info_dict = TTLCache(maxsize=2, ttl=600)

    group_member_list = TTLCache(maxsize=20, ttl=3600)
    stranger_cache = TTLCache(maxsize=100, ttl=3600)

    def __init__(self, client_id: str, config: Dict[str, Any], channel):
        super().__init__(client_id, config)
        self.client_config = config[self.client_id]
        self.uin = self.client_config['qq']
        self.host = self.client_config.get('host', 'http://127.0.0.1')
        self.port = self.client_config.get('port', 8888)
        IOTConfig.configs = self.client_config
        self.bot = Botoy(qq=self.uin, host=self.host, port=self.port)
        self.action = Action(qq=self.uin, host=self.host, port=self.port)
        IOTFactory.bot = self.bot
        IOTFactory.action = self.action
        self.channel = channel
        ChatMgr.slave_channel = channel
        self.iot_msg = IOTMsgProcessor(self.uin)

        @self.bot.when_connected
        def on_ws_connected():
            self.logger.info("Connected to OPQBot!")

        @self.bot.when_disconnected
        def on_ws_disconnected():
            self.logger.info("Disconnected from OPQBot!")

        @self.bot.on_friend_msg
        def on_friend_msg(ctx: FriendMsg):
            self.logger.debug(ctx)
            if int(ctx.FromUin) == int(self.uin) and not IOTConfig.configs.get('receive_self_msg', True):
                self.logger.info("Received self message and flag set. Cancel delivering...")
                return
            remark_name = self.get_friend_remark(ctx.FromUin)
            if not remark_name:
                info = self.get_stranger_info(ctx.FromUin)
                if info:
                    remark_name = info.get('nickname', '')
                else:
                    remark_name = str(ctx.FromUin)
            if ctx.MsgType == 'TempSessionMsg':  # Temporary chat
                chat_uid = f'private_{ctx.FromUin}_{ctx.TempUin}'
            elif ctx.MsgType == 'PhoneMsg':
                chat_uid = f'phone_{ctx.FromUin}'
            else:
                chat_uid = f'friend_{ctx.FromUin}'
            chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                uid=chat_uid,
                name=remark_name,
            ))
            author = chat.other

            # Splitting messages
            messages: List[Message] = []
            func = getattr(self.iot_msg, f'iot_{ctx.MsgType}_friend')
            messages.extend(func(ctx, chat))

            # Sending messages one by one
            message_id = ctx.MsgSeq
            for idx, val in enumerate(messages):
                if not isinstance(val, Message):
                    continue
                val.uid = f"friend_{ctx.FromUin}_{message_id}_{idx}"
                val.chat = chat
                val.author = author
                val.deliver_to = coordinator.master
                coordinator.send_message(val)
                if val.file:
                    val.file.close()

        @self.bot.on_group_msg
        def on_group_msg(ctx: GroupMsg):
            # OPQbot has no indicator for anonymous user, so we have to test the uin
            nickname = ctx.FromNickName
            if int(ctx.FromUserId) == int(self.uin) and not IOTConfig.configs.get('receive_self_msg', True):
                self.logger.info("Received self message and flag set. Cancel delivering...")
                return
            remark_name = self.get_friend_remark(ctx.FromUserId)
            if not remark_name:
                info = self.get_stranger_info(ctx.FromUserId)
                if info:
                    remark_name = info.get('nickname', '')
            chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                uid=f"group_{ctx.FromGroupId}",
                name=ctx.FromGroupName
            ))
            author = ChatMgr.build_efb_chat_as_member(chat, EFBGroupMember(
                name=nickname,
                alias=remark_name,
                uid=str(ctx.FromUserId)
            ))
            # Splitting messages
            messages: List[Message] = []
            func = getattr(self.iot_msg, f'iot_{ctx.MsgType}_group')
            messages.extend(func(ctx, chat))

            # Sending messages one by one
            message_id = ctx.MsgSeq
            for idx, val in enumerate(messages):
                if not isinstance(val, Message):
                    continue
                val.uid = f"group_{ctx.FromGroupId}_{message_id}_{idx}"
                val.chat = chat
                val.author = author
                val.deliver_to = coordinator.master
                coordinator.send_message(val)
                if val.file:
                    val.file.close()

        @self.bot.on_event
        def on_event(ctx: EventMsg):
            pass  # fixme

    def login(self):
        pass

    def logout(self):
        self.action.logout()

    def relogin(self):
        pass

    def send_message(self, msg: 'Message') -> 'Message':
        chat_info = msg.chat.uid.split('_')
        chat_type = chat_info[0]
        chat_uid = chat_info[1]
        if msg.edit:
            pass  # todo Revoke message & resend

        if msg.type in [MsgType.Text, MsgType.Link]:
            if isinstance(msg.target, Message):  # Reply to message
                max_length = 50
                tgt_alias = iot_at_user(msg.target.author.uid)
                tgt_text = process_quote_text(msg.target.text, max_length)
                msg.text = "%s%s\n\n%s" % (tgt_alias, tgt_text, msg.text)
            self.iot_send_text_message(chat_type, chat_uid, msg.text)
            msg.uid = str(uuid.uuid4())
            self.logger.debug('[%s] Sent as a text message. %s', msg.uid, msg.text)
        elif msg.type in (MsgType.Image, MsgType.Sticker, MsgType.Animation):
            self.logger.info("[%s] Image/Sticker/Animation %s", msg.uid, msg.type)
            self.iot_send_image_message(chat_type, chat_uid, msg.file, msg.text)
            msg.uid = str(uuid.uuid4())
        elif msg.type is MsgType.Voice:
            self.logger.info(f"[{msg.uid}] Voice.")
            if not VOICE_SUPPORTED:
                self.iot_send_text_message(chat_type, chat_uid, "[语音消息]")
            else:
                pydub.AudioSegment.from_file(msg.file).export(msg.file, format='s16le',
                                                              parameters=["-ac", "1", "-ar", "24000"])
                output_file = tempfile.NamedTemporaryFile()
                if not Silkv3.encode(msg.file.name, output_file.name):
                    self.iot_send_text_message(chat_type, chat_uid, "[语音消息]")
                else:
                    self.iot_send_voice_message(chat_type, chat_uid, output_file)
                if msg.text:
                    self.iot_send_text_message(chat_type, chat_uid, msg.text)
            msg.uid = str(uuid.uuid4())
        return msg

    def send_status(self, status: 'Status'):
        raise NotImplementedError

    def receive_message(self):
        # replaced by on_*
        pass

    def get_friends(self) -> List['Chat']:
        if not self.info_list.get('friend', None):
            self.update_friend_list()
        friends = []
        self.info_dict['friend'] = {}
        for friend in self.info_list.get('friend', []):
            friend_uin = friend['FriendUin']
            friend_name = friend['NickName']
            friend_remark = friend['Remark']
            new_friend = EFBPrivateChat(
                uid=f"friend_{friend_uin}",
                name=friend_name,
                alias=friend_remark
            )
            self.info_dict['friend'][friend_uin] = friend
            friends.append(ChatMgr.build_efb_chat_as_private(new_friend))
        return friends

    def get_groups(self) -> List['Chat']:
        if not self.info_list.get('group', None):
            self.update_group_list()
        groups = []
        self.info_dict['group'] = {}
        for group in self.info_list.get('group', []):
            group_name = group['GroupName']
            group_id = group['GroupId']
            new_group = EFBGroupChat(
                uid=f"group_{group_id}",
                name=group_name
            )
            self.info_dict['group'][group_id] = IOTGroup(group)
            groups.append(ChatMgr.build_efb_chat_as_group(new_group))
        return groups

    def get_login_info(self) -> Dict[Any, Any]:
        pass

    def get_stranger_info(self, user_id) -> Union[Dict, None]:
        if not self.stranger_cache.get(user_id, None):
            response = self.action.getUserInfo(user=user_id)
            if response.get('code', 1) != 0:  # Failed to get info
                return None
            else:
                self.stranger_cache[user_id] = response.get('data', None)
        return self.stranger_cache.get(user_id)

    def get_group_info(self, group_id: int, no_cache=True) -> Union[None, IOTGroup]:
        if no_cache or not self.info_dict.get('group', None):
            self.update_group_list()
        return self.info_dict['group'].get(group_id, None)

    def get_chat_picture(self, chat: 'Chat') -> BinaryIO:
        chat_type = chat.uid.split('_')
        if chat_type[0] == 'private':
            private_uin = chat_type[1].split('_')[0]
            return download_user_avatar(private_uin)
        elif chat_type[0] == 'friend':
            return download_user_avatar(chat_type[1])
        elif chat_type[0] == 'group':
            return download_group_avatar(chat_type[1])

    def get_chat(self, chat_uid: ChatID) -> 'Chat':
        chat_info = chat_uid.split('_')
        chat_type = chat_info[0]
        chat_attr = chat_info[1]
        chat = None
        if chat_type == 'friend':
            chat_uin = int(chat_attr)
            remark_name = self.get_friend_remark(chat_uin)
            chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                uid=chat_attr,
                name=remark_name if remark_name else "",
            ))
        elif chat_type == 'group':
            chat_uin = int(chat_attr)
            group_info = self.get_group_info(chat_uin, no_cache=False)
            group_members = self.get_group_member_list(chat_uin, no_cache=False)
            chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                uid=f"group_{chat_uin}",
                name=group_info.get('GroupName', "")
            ), group_members)
        elif chat_type == 'private':
            pass  # fixme
        elif chat_type == 'phone':
            pass  # fixme
        return chat

    def get_chats(self) -> Collection['Chat']:
        return self.get_friends() + self.get_groups()

    def get_group_member_list(self, group_id, no_cache=True):
        if no_cache \
                or not self.group_member_list.get(group_id, None):  # Key expired or not exists
            # Update group member list
            group_members = self.action.getGroupMembers(group_id)
            efb_group_members: List[EFBGroupMember] = []
            for qq_member in group_members:
                qq_member = IOTGroupMember(qq_member)
                efb_group_members.append(EFBGroupMember(
                    name=qq_member['NickName'],
                    alias=qq_member['GroupCard'],
                    uid=qq_member['MemberUin']
                ))
            self.group_member_list[group_id] = efb_group_members
        return self.group_member_list[group_id]

    def poll(self):
        threading.Thread(target=self.bot.run, daemon=True).start()
        # self.bot.run()

    def stop_polling(self):
        self.bot.close()

    def update_friend_list(self):
        """
        Update friend list from OPQBot

        """
        self.info_list['friend'] = self.action.getUserList()

    def update_group_list(self):
        self.info_list['group'] = self.action.getGroupList()

    def get_friend_remark(self, uin: int) -> Union[None, str]:
        count = 0
        while count <= 1:
            if not self.info_list.get('friend', None):
                self.update_friend_list()
                self.get_friends()
                count += 1
            else:
                break
        if count > 1:  # Failure or friend not found
            raise Exception("Failed to update friend list!")  # todo Optimize error handling
        if not self.info_dict.get('friend', None) or uin not in self.info_dict['friend']:
            return None
        # When there is no mark available, the OPQBot API will fill the remark field with nickname
        # Thus no need to test whether isRemark is true or not
        return self.info_dict['friend'][uin].get('Remark', None)

    def iot_send_text_message(self, chat_type: str, chat_uin: str, content: str):
        if chat_type == 'phone':  # Send text to self
            self.action.sendPhoneText(content)
        elif chat_type == 'group':
            chat_uin = int(chat_uin)
            self.action.sendGroupText(chat_uin, content)
        elif chat_type == 'friend':
            chat_uin = int(chat_uin)
            self.action.sendFriendText(chat_uin, content)
        elif chat_type == 'private':
            user_info = chat_uin.split('_')
            chat_uin = int(user_info[0])
            chat_origin = int(user_info[1])
            self.action.sendPrivateText(chat_uin, chat_origin, content)

    def iot_send_image_message(self, chat_type: str, chat_uin: str, file: IO, content: Union[str, None] = None):
        image_base64 = base64.b64encode(file.read()).decode("UTF-8")
        md5_sum = hashlib.md5(file.read()).hexdigest()
        content = content if content else ""
        if chat_type == 'private':
            user_info = chat_uin.split('_')
            chat_uin = int(user_info[0])
            chat_origin = int(user_info[1])
            self.action.sendPrivatePic(user=chat_uin, group=chat_origin, picBase64Buf=image_base64,
                                       fileMd5=md5_sum, content=content)
        elif chat_type == 'friend':
            chat_uin = int(chat_uin)
            self.action.sendFriendPic(user=chat_uin, picBase64Buf=image_base64, fileMd5=md5_sum, content=content)
        elif chat_type == 'group':
            chat_uin = int(chat_uin)
            self.action.sendGroupPic(group=chat_uin, picBase64Buf=image_base64, fileMd5=md5_sum, content=content)

    def iot_send_voice_message(self, chat_type: str, chat_uin: str, file: IO):
        voice_base64 = base64.b64encode(file.read()).decode("UTF-8")
        if chat_type == 'private':
            user_info = chat_uin.split('_')
            chat_uin = int(user_info[0])
            chat_origin = int(user_info[1])
            self.action.sendPrivateVoice(user=chat_uin, group=chat_origin, voiceBase64Buf=voice_base64)
        elif chat_type == 'friend':
            chat_uin = int(chat_uin)
            self.action.sendFriendVoice(user=chat_uin, voiceBase64Buf=voice_base64)
        elif chat_type == 'group':
            chat_uin = int(chat_uin)
            self.action.sendGroupVoice(group=chat_uin, voiceBase64Buf=voice_base64)