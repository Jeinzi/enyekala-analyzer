# The MIT License (MIT)
# Copyright (c) 2025 Julian Heinzel
# Copyright (c) 2016 TenPlus1
# https://github.com/BluebirdGreycoat/musttest_game/src/master/mods/mobs
import re

#import helpers


kill_adj = [
	"killed",
	"slain",
	"slaughtered",
	"mauled",
	"murdered",
	"pwned",
	"owned",
	"dispatched",
	"neutralized",
	"wasted",
	"polished off",
	"rubbed out",
	"snuffed out",
	"assassinated",
	"annulled",
	"destroyed",
	"finished off",
	"terminated",
	"wiped out",
	"scrubbed",
	"abolished",
	"obliterated",
	"voided",
	"ended",
	"annihilated",
	"undone",
	"nullified",
	"exterminated",
]

kill_adj2 = [
	"killed",
	"slew",
	"slaughtered",
	"mauled",
	"murdered",
	"pwned",
	"owned",
	"dispatched",
	"neutralized",
	"wasted",
	"polished off",
	"rubbed out",
	"snuffed out",
	"assassinated",
	"annulled",
	"destroyed",
	"finished off",
	"terminated",
	"wiped out",
	"scrubbed",
	"abolished",
	"obliterated",
	"voided",
	"ended",
	"annihilated",
	"undid",
	"nullified",
	"exterminated",
]

kill_adj3 = [
	"kill",
	"slay",
	"slaughter",
	"maul",
	"murder",
	"pwn",
	"own",
	"dispatch",
	"neutralize",
	"waste",
	"polish off",
	"rub out",
	"snuff out",
	"assassinate",
	"annul",
	"destroy",
	"finish off",
	"terminate",
	"wipe out",
	"scrub",
	"abolish",
	"obliterate",
	"void",
	"end",
	"annihilate",
	"undo",
	"nullify",
	"exterminate",
]

# Might also be an empty string.
kill_adv = [
	"brutally",
	"swiftly",
	"savagely",
	"viciously",
	"uncivilly",
	"barbarously",
	"ruthlessly",
	"ferociously",
	"rudely",
	"cruelly",
]

# Might also be an empty string.
kill_ang = [
	"angry",
	"PO'ed",
	"furious",
	"disgusted",
	"infuriated",
	"annoyed",
	"irritated",
	"bitter",
	"offended",
	"outraged",
	"irate",
	"enraged",
	"indignant",
	"irritable",
	"cross",
	"riled",
	"vexed",
	"wrathful",
	"fierce",
	"displeased",
	"irascible",
	"ireful",
	"sulky",
	"ill-tempered",
	"vehement",
	"raging",
	"incensed",
	"frenzied",
	"enthusiastic",
	"fuming",
	"cranky",
	"peevish",
	"belligerent",
]

pain_words = [
	"harm",
	"pain",
	"grief",
	"trouble",
	"evil",
	"ill will",
]

murder_messages = [
	"<n> <v> collapsed from <an_angry_k>'s <angry>attack.",
	"<an_angry_k>'s <w> apparently wasn't such an unusual weapon after all, as <n> <v> found out.",
	"<an_angry_k> <brutally><slew> <n> <v> with great prejudice.",
	"<n> <v> died from <an_angry_k>'s horrid slaying.",
	"<n> <v> fell prey to <an_angry_k>'s deadly <w>.",
	"<an_angry_k> went out of <k_his> way to <slay> <n> <v> with <k_his> <w>.",
	"<n> <v> danced <v_himself> to death under <an_angry_k>'s craftily wielded <w>.",
	"<an_angry_k> used <k_his> <w> to <slay> <n> <v> with prejudice.",
	"<an_angry_k> made a splortching sound with <n> <v>'s head.",
	"<n> <v> was <slain> by <an_angry_k>'s skillfully handled <w>.",
	"<n> <v> became prey for <an_angry_k>.",
	"<n> <v> didn't get out of <an_angry_k>'s way in time.",
	"<n> <v> SAW <an_angry_k> coming with <k_his> <w>. Didn't get away in time.",
	"<n> <v> made no real attempt to get out of <an_angry_k>'s way.",
	"<an_angry_k> barreled through <n> <v> as if <v_he> wasn't there.",
	"<an_angry_k> sent <n> <v> to that place where kindling wood isn't needed.",
	"<n> <v> didn't suspect that <an_angry_k> meant <v_him> any <pain>.",
	"<n> <v> fought <an_angry_k> to the death and lost painfully.",
	"<n> <v> knew <an_angry_k> was wielding <k_his> <w> but didn't guess what <k> meant to do with it.",
	"<an_angry_k> <brutally>clonked <n> <v> over the head using <k_his> <w> with silent skill.",
	"<an_angry_k> made sure <n> <v> didn't see that coming!",
	"<an_angry_k> has decided <k_his> favorite weapon is <k_his> <w>.",
	"<n> <v> did the mad hatter dance just before being <slain> with <an_angry_k>'s <w>.",
	"<n> <v> played the victim to <an_angry_k>'s bully behavior!",
	"<an_angry_k> used <n> <v> for weapons practice with <k_his> <w>.",
	"<n> <v> failed to avoid <an_angry_k>'s oncoming weapon.",
	"<an_angry_k> successfully got <n> <v> to complain of a headache.",
	"<n> <v> got <v_himself> some serious hurt from <an_angry_k>'s <w>.",
	"Trying to talk peace to <an_angry_k> didn't win any for <n> <v>.",
	"<n> <v> was <brutally><slain> by <an_angry_k>'s <w>.",
	"<n> <v> jumped the mad-hatter dance under <an_angry_k>'s <w>.",
	"<n> <v> got <v_himself> a fatal mauling by <an_angry_k>'s <w>.",
	"<an_angry_k> <brutally><slew> <n> <v> with <k_his> <w>.",
	"<an_angry_k> split <n> <v>'s wig.",
	"<an_angry_k> took revenge on <n> <v>.",
	"<an_angry_k> <brutally><slew> <n> <v>.",
	"<n> <v> played dead. Permanently.",
	"<n> <v> never saw what hit <v_him>.",
	"<an_angry_k> took <n> <v> by surprise.",
	"<n> <v> was <brutally><slain>.",
	"<an_angry_k> didn't take any prisoners from <n> <v>.",
	"<an_angry_k> <brutally>pinned <n> <v> to the wall with <k_his> <w>.",
	"<n> <v> failed <v_his> weapon checks.",
	"<k> eliminated <n> <v>.",
]



def parseMobMessages(d, l):
  # ToDo: Don't duplicate date regex.
  dateRegexNew = r"^\[(\d{4})/(\d{2})/(\d{2}), (\d{2}):(\d{2}):(\d{2}) UTC\][ ]*"

  killAdjGroup = "(" + "|".join(kill_adj) + ")"
  killAngGroup = "(" + "|".join(kill_ang) + ")"

  # Example
  # [2019/07/07, 16:07:25 UTC]    Server: <AyabelleFeu> was viciously wasted by an irascible Black-Hearted Oerkki.
  pattern = dateRegexNew + fr"# Server: <(.*?)> was(.*)? {killAdjGroup} by an? ?{killAngGroup}? (.*?)\.$"
  res = re.search(pattern, l)
  if res:
    name = res.groups()[6]
    mob = res.groups()[10]

    helpers.createPlayer(d, name)
    mobArray = d[name]["deathsByMob"]
    if not mobArray.get(mob):
      mobArray[mob] = 1
    else:
      mobArray[mob] += 1
    return True

  return False



def parseDeadMobs(d, l):
  # Bugs:
  # A displeased <Sanith> ruthlessly scrubbed a Flying Menace with his 'Amethyst Sword'
  killAdjGroup = "(" + "|".join(kill_adj) + ")"
  killAdj2Group = "(" + "|".join(kill_adj2) + ")"
  killAdj3Group = "(" + "|".join(kill_adj3) + ")"
  killAngGroup = "(" + "|".join(kill_ang) + ")"
  killAdvGroup = "(" + "|".join(kill_adv) + ")"
  painGroup = "(" + "|".join(pain_words) + ")"

  for i in range(len(murder_messages)):
    m = murder_messages[i]
    m = m.replace("<k_himself>", "(himself|herself|itself)")
    m = m.replace("<k_his>", "(his|her|its)")

    m = m.replace("<v_himself>", "(himself|herself|itself)")
    m = m.replace("<v_his>", "(his|her|its)")
    m = m.replace("<v_him>", "(him)")
    m = m.replace("<v_he>", "(he)")
    m = m.replace("<n>", "[Aa]n?")

    m = m.replace("<brutally>", f"({killAdvGroup} )?")
    m = m.replace("<angry>", f"({killAngGroup} )?")

    m = m.replace("<an_angry_k>", f"([Aa]n? {killAngGroup} )?<(.*)>")

    m = m.replace("<slain>", killAdjGroup)
    m = m.replace("<slew>", killAdj2Group)
    m = m.replace("<slay>", killAdj3Group)
    m = m.replace("<pain>", painGroup)

    m = m.replace("<w>", "(.*)")
    m = m.replace("<v>", "(.*)")
    m = m.replace("<k>", "(.*)")

    murder_messages[i] = m

  #print(murder_messages[5])
  for m in murder_messages:
    res = re.search(m, l)
    if res:
      return True
  return False
