using System;
using System.Collections.Concurrent;
using BepInEx;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;
using TMPro;

namespace SuzerainAltTFix
{
    [BepInPlugin("com.asciihorse.suzerainmod.alttfix", "Suzerain IL2CPP Alt-T Fix", "1.0.0")]
    public class Plugin : BasePlugin
    {
        public static readonly ConcurrentDictionary<int, string> OriginalEnglishStore = new ConcurrentDictionary<int, string>();

        public override void Load()
        {
            var harmony = new Harmony("com.asciihorse.suzerainmod.alttfix");
            harmony.PatchAll();
            Log.LogInfo("=== [Fix] Text-Getter hook via InstanceID activated successfully! ===");
        }

        // Hook into text assignment (setter)
        [HarmonyPatch(typeof(TMP_Text), nameof(TMP_Text.text), MethodType.Setter)]
        public static class TMP_Text_Setter_Patch
        {
            public static void Prefix(TMP_Text __instance, string value)
            {
                if (__instance == null || string.IsNullOrEmpty(value)) return;

                // If the incoming text is original English (no Cyrillic), cache it under the object's unique ID
                if (!ContainsCyrillic(value))
                {
                    OriginalEnglishStore[__instance.GetInstanceID()] = value;
                }
            }
        }

        // Hook into text retrieval (getter)
        [HarmonyPatch(typeof(TMP_Text), nameof(TMP_Text.text), MethodType.Getter)]
        public static class TMP_Text_Getter_Patch
        {
            public static bool Prefix(TMP_Text __instance, ref string __result)
            {
                if (__instance == null) return true;

                // When the game reads text (e.g., for hover mutations), force-feed it the cached English version
                if (OriginalEnglishStore.TryGetValue(__instance.GetInstanceID(), out string originalEnglish))
                {
                    __result = originalEnglish;
                    return false; // Skip the original game getter to protect XUnity's cache from contamination
                }
                return true;
            }
        }

        private static bool ContainsCyrillic(string text)
        {
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (c >= 0x0400 && c <= 0x04FF)
                {
                    return true;
                }
            }
            return false;
        }
    }
}