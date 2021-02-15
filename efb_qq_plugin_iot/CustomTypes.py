
from typing import Optional, Dict

from ehforwarderbot.channel import SlaveChannel


class EFBGroupChat(Dict):
    channel: str
    uid: str
    name: str


class EFBPrivateChat(EFBGroupChat):
    alias: str


class EFBGroupMember(Dict):
    name: str
    uid: str
    alias: str


class IOTGroup(Dict):
    GroupId: str
    GroupMemberCount: int
    GroupName: str
    GroupNotice: str
    GroupOwner: str
    GroupTotalCount: int


class IOTFriend(Dict):
    FriendUin: str
    IsRemark: bool
    NickName: str
    Remark: str
    Status: int


class IOTGroupMember(Dict):
    Age: int
    AutoRemark: str
    CreditLevel: int
    Email: int
    FaceId: int
    Gender: int
    GroupAdmin: int
    GroupCard: str
    JoinTime: int
    LastSpeakTime: int
    MemberLevel: int
    MemberUin: int
    Memo: str
    NickName: str  # May be remark name if already been a friend
    ShowName: str
    SpecialTitle: str
    Status: int
