// Dumps PKHeX data to build/raw.json. Usage: Exporter <games.json> <out.json>
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using PKHeX.Core;

// Those forms get their own key (ContextFormBase + index) so their encounters never land on the modern form.
const int ContextFormBase = 100;

if (args.Length != 2)
    return Fail("usage: Exporter <games.json> <out.json>");

var groups = LoadGroups(args[0]);
if (groups is null)
    return 1;

var strings = GameInfo.GetStrings("en");
var (species, megas) = ExportSpecies(groups.Where(g => !g.Other).ToList(), strings);
var clock = System.Diagnostics.Stopwatch.StartNew();
var encounters = ExportEncounters(groups, species);
Console.Error.WriteLine($"encounters: {encounters.Count} in {clock.Elapsed.TotalSeconds:F1}s");

var evolutions = ExportEvolutions(groups, species);
Console.Error.WriteLine($"evolutions: {evolutions.Count}");

var root = new JsonObject
{
    ["pkhex"] = typeof(PKM).Assembly.GetName().Version is { } v ? $"{v.Major}.{v.Minor}.{v.Build}" : "?",
    ["species"] = species,
    ["megas"] = megas,
    ["encounters"] = encounters,
    ["evolutions"] = evolutions,
};
Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(args[1]))!);
File.WriteAllText(args[1], root.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
return 0;

static int Fail(string message)
{
    Console.Error.WriteLine(message);
    return 1;
}

static List<Group>? LoadGroups(string path)
{
    var list = new List<Group>();
    var tables = typeof(PersonalTable).GetFields(BindingFlags.Public | BindingFlags.Static);
    foreach (var g in JsonNode.Parse(File.ReadAllText(path))!["groups"]!.AsArray())
    {
        var id = (string)g!["id"]!;
        var personalName = (string)g["personal"]!;
        var blank = (string)g["blank"]!;
        if (typeof(PKM).Assembly.GetType($"PKHeX.Core.{blank}") is not { } type || !type.IsSubclassOf(typeof(PKM)))
        { Console.Error.WriteLine($"{id}: unknown blank '{blank}'"); return null; }
        foreach (var ver in g["versions"]!.AsArray())
        {
            var code = (string)ver!["code"]!;
            if (code != "GO" && !Enum.GetNames<GameVersion>().Contains(code))
            { Console.Error.WriteLine($"{id}: unknown GameVersion code '{code}'"); return null; }
        }
        var versions = g["versions"]!.AsArray().Select(x => (string)x!["code"]!).ToArray();
        if (g["other"]?.GetValue<bool>() == true)
        {   // pseudo-group (GO): no per-form presence; personal table is only a placeholder
            list.Add(new Group(id, PersonalTable.SV, type, versions, true));
            continue;
        }
        if (tables.FirstOrDefault(f => f.Name == personalName)?.GetValue(null) is not IPersonalTable table)
        { Console.Error.WriteLine($"{id}: unknown personal table '{personalName}'"); return null; }
        list.Add(new Group(id, table, type, versions, false));
    }
    return list;
}

// PKHeX form indices that mean a different form in some games than in later ones (see ContextFormBase).
static (ushort Species, EntityContext Context, string[] Groups, int[] Forms)[] ContextForms() =>
[
    (25, EntityContext.Gen6, ["ORAS"], [1, 2, 3, 4, 5, 6]),   // Cosplay Pikachu; from Gen 7 these indices are the caps
    (172, EntityContext.Gen4, ["DPPt", "HGSS"], [1]),          // Spiky-eared Pichu; no form 1 in later games
];

static (JsonArray, JsonObject) ExportSpecies(List<Group> groups, GameStrings strings)
{
    // Form names depend on context (Megas only list in Gen 6/7/9a); take the union.
    EntityContext[] contexts = [EntityContext.Gen9, EntityContext.Gen9a, EntityContext.Gen8, EntityContext.Gen8a,
        EntityContext.Gen8b, EntityContext.Gen7, EntityContext.Gen7b, EntityContext.Gen6];
    var result = new JsonArray();
    var megas = new JsonObject();
    var max = Math.Max(PersonalTable.SV.MaxSpeciesID, PersonalTable.ZA.MaxSpeciesID);
    for (ushort sp = 1; sp <= max; sp++)
    {
        var names = new SortedDictionary<int, string>();
        foreach (var ctx in contexts)
        {
            var list = FormConverter.GetFormList(sp, strings.types, strings.forms, ctx);
            for (var i = 0; i < list.Length; i++)
                if (!names.TryGetValue(i, out var n) || (n.Length == 0 && list[i].Length != 0))
                    names[i] = list[i];
        }
        names[0] = names.GetValueOrDefault(0) is null or "Normal" ? "" : names[0]; // base form: PKHeX says "Normal" for most
        var forms = new JsonArray();
        foreach (var (f, name) in names)
        {
            var form = (byte)f;
            var present = new JsonArray();
            foreach (var g in groups)
                if (g.Table.IsPresentInGame(sp, form))
                    present.Add(g.Id);
            forms.Add(new JsonObject
            {
                ["form"] = f,
                ["name"] = name,
                ["battle_only"] = FormInfo.IsBattleOnlyForm(sp, form, 9),
                ["fused"] = FormInfo.IsFusedForm(sp, form, 9),
                ["groups"] = present,
            });
            // Z-A names the Mega of a non-base form "<form>-Mega" (Meowstic, Tatsugiri, Magearna): list it once as "Mega"
            var mega = name.EndsWith("-Mega", StringComparison.Ordinal) ? "Mega" : name;
            var list0 = (megas[sp.ToString()] ??= new JsonArray()).AsArray();
            if (mega.StartsWith("Mega", StringComparison.Ordinal) && !list0.Any(x => (string)x! == mega))
                list0.Add(mega);
            if (list0.Count == 0)
                megas.Remove(sp.ToString());
        }
        foreach (var (cs, ctx, cgroups, cforms) in ContextForms().Where(c => c.Species == sp))
        {
            var list = FormConverter.GetFormList(sp, strings.types, strings.forms, ctx);
            foreach (var f in cforms)
            {
                // the modern form with this index is not in these games
                if (forms.FirstOrDefault(x => (int)x!["form"]! == f) is { } modern)
                    foreach (var g in modern["groups"]!.AsArray().Where(x => cgroups.Contains((string)x!)).ToList())
                        modern["groups"]!.AsArray().Remove(g);
                forms.Add(new JsonObject
                {
                    ["form"] = ContextFormBase + f,
                    ["pkhex_form"] = f,
                    ["name"] = list[f],
                    ["battle_only"] = false,
                    ["fused"] = false,
                    ["groups"] = new JsonArray(cgroups.Select(x => (JsonNode)x).ToArray()),
                });
            }
        }
        result.Add(new JsonObject { ["id"] = sp, ["name"] = strings.specieslist[sp], ["forms"] = forms });
    }
    return (result, megas);
}

static JsonArray ExportEncounters(List<Group> groups, JsonArray species)
{
    var found = new SortedDictionary<string, JsonObject>(StringComparer.Ordinal);
    // language copies of one gift card share a card id; PKHeX lists the English copy first when there is one
    var titles = new Dictionary<(int, ushort, int), string>();
    for (var gi = 0; gi < groups.Count; gi++)
    {
        var g = groups[gi];
        var codes = g.Versions.Select(Enum.Parse<GameVersion>).ToArray();
        var blank = NewBlank(g.Blank);
        foreach (var sp in species)
        {
            var id = sp!["id"]!.GetValue<ushort>();
            if (id > blank.MaxSpeciesID)
                continue;
            var forms = sp["forms"]!.AsArray().Where(f => g.Other
                ? !f!["battle_only"]!.GetValue<bool>() && f["pkhex_form"] is null
                : f!["groups"]!.AsArray().Any(x => (string)x! == g.Id)).Select(f => (byte)(f!["pkhex_form"] ?? f["form"])!.GetValue<int>()).ToList();
            if (forms.Count == 0 && !g.Other)
                forms.Add(0);
            var ctxForms = ContextForms().Where(c => c.Species == id && c.Groups.Contains(g.Id)).SelectMany(c => c.Forms).ToHashSet();
            foreach (var form in forms)
            {
                var pk = NewBlank(g.Blank);
                pk.Species = id;
                pk.Form = form;
                foreach (var enc in EncounterMovesetGenerator.GenerateEncounters(pk, ReadOnlyMemory<ushort>.Empty, codes))
                {
                    if (enc.Species != id)
                        continue; // generator also walks back to pre-evolutions
                    var vers = g.Versions.Where(c => enc.Version.Contains(Enum.Parse<GameVersion>(c))).ToArray();
                    if (enc is EncounterTera9 tera) // a player alone can only host the raids of their own version
                        vers = vers.Where(c => c == "SL" ? tera.IsAvailableHostScarlet : tera.IsAvailableHostViolet).ToArray();
                    if (vers.Length == 0)
                        continue;
                    var formKey = ctxForms.Contains(enc.Form) ? ContextFormBase + enc.Form : enc.Form;
                    var o = new JsonObject
                    {
                        ["group"] = g.Id,
                        ["species"] = (int)id,
                        ["form"] = formKey,
                        ["form_random"] = enc.Form is 30 or 31, // EncounterUtil FormDynamic / FormVivillon markers
                        ["type"] = enc.GetType().Name,
                        ["label"] = enc.Name,
                        ["versions"] = new JsonArray(vers.Select(v => (JsonNode)v).ToArray()),
                        ["location"] = enc.GetEncounterLocation(enc.Generation, enc.Version) ?? "",
                        ["egg"] = enc.IsEgg,
                        ["area"] = enc is EncounterTera9 t9 ? t9.Map.ToString() : null,
                        ["event_title"] = enc is MysteryGift { CardTitle: { Length: > 0 } t } c
                            ? (titles.TryAdd((gi, id, c.CardID), t) ? t : titles[(gi, id, c.CardID)]) : null,
                        ["event_id"] = enc is MysteryGift mg ? mg.CardID : null,
                        ["event_year"] = EventYear(enc),
                        ["gender"] = enc is IFixedGender { IsFixedGender: true } fg ? (fg.Gender == 0 ? "m" : fg.Gender == 1 ? "f" : null) : null,
                    };
                    var key = $"{gi:D2}|{id:D4}|{formKey:D3}|{o["type"]}|{o["location"]}|{o.ToJsonString()}";
                    found.TryAdd(key, o);
                }
            }
        }
    }
    return new JsonArray(found.Values.Select(v => (JsonNode)v).ToArray());
}
// Year a gift card was given out, where PKHeX knows it (nothing for Gen 4 and earlier).
static int? EventYear(IEncounterable enc)
{
    DistributionWindow w = default;
    int? year = enc switch
    {
        WC6 g => g.Date?.Year is >= 2013 and <= 2020 and var y ? y : null, // undated cards read as today or as a default year
        WC7 g => g.Date?.Year is >= 2016 and <= 2020 and var y ? y : null,
        PGF g => g.Date?.Year,
        WB7 g => g.Date?.Year,
        WC8 g when EncounterServerDate.GetDistributionWindow(g, out w) => w.Start.Year,
        WA8 g when EncounterServerDate.GetDistributionWindow(g, out w) => w.Start.Year,
        WB8 g when EncounterServerDate.GetDistributionWindow(g, out w) => w.Start.Year,
        WC9 g when EncounterServerDate.GetDistributionWindow(g, out w) => w.Start.Year,
        WA9 g when EncounterServerDate.GetDistributionWindow(g, out w) => w.Start.Year,
        _ => null,
    };
    return year is >= 2010 and <= 2100 ? year : null; // an unset card date reads as year 2000
}

static JsonArray ExportEvolutions(List<Group> groups, JsonArray species)
{
    var result = new JsonArray();
    foreach (var g in groups.Where(g => !g.Other))
    {
        var tree = EvolutionTree.GetEvolutionTree(NewBlank(g.Blank).Context);
        var present = new HashSet<(int, int)>();
        foreach (var sp in species)
            // context forms (Cosplay Pikachu, Spiky-eared Pichu) do not evolve
            foreach (var f in sp!["forms"]!.AsArray().Where(f => f!["pkhex_form"] is null && f["groups"]!.AsArray().Any(x => (string)x! == g.Id)))
                present.Add(((int)sp["id"]!.GetValue<ushort>(), (int)f!["form"]!));
        foreach (var (id, form) in present.Order())
        {
            // several methods can reach one target (e.g. by item or by level): it is a trade edge only if all of them are
            var edges = new SortedDictionary<(int, int), bool>();
            // versions an edge is limited to (Cosmoem, Gen 7 Rockruff); absent = every version
            var limits = new Dictionary<(int, int), HashSet<string>?>();
            foreach (var m in tree.Forward.GetForward((ushort)id, (byte)form).Span)
            {
                if (m.Species == 0)
                    continue;
                // Ultra Wormhole methods share the Gen 7 tree with SM, but the Wormhole only exists in US/UM
                if (m.Method is EvolutionType.LevelUpWormhole or EvolutionType.UseItemWormhole && !g.Versions.Any(v => v is "US" or "UM"))
                    continue;
                var to = (m.Species, (int)m.GetDestinationForm((byte)form));
                if (!present.Contains(to))
                    continue;
                edges[to] = edges.GetValueOrDefault(to, true) && m.Method.IsTrade;
                // PKHeX keeps a version-bound method's version in Argument and compares its parity with the game's
                var only = m.Method is EvolutionType.LevelUpVersion or EvolutionType.LevelUpVersionDay or EvolutionType.LevelUpVersionNight
                    ? g.Versions.Where(v => ((int)Enum.Parse<GameVersion>(v) & 1) == (m.Argument & 1)).ToHashSet() : null;
                if (only is null || !limits.TryGetValue(to, out var cur))
                    limits[to] = only;
                else
                    cur?.UnionWith(only);
            }
            foreach (var ((ts, tf), trade) in edges)
                result.Add(new JsonObject
                {
                    ["group"] = g.Id, ["from"] = new JsonArray(id, form), ["to"] = new JsonArray(ts, tf), ["trade"] = trade,
                    ["versions"] = limits[(ts, tf)] is { } l ? new JsonArray(g.Versions.Where(l.Contains).Select(v => (JsonNode)v).ToArray()) : null,
                });
        }
    }
    return result;
}

static PKM NewBlank(Type t) => (PKM)Activator.CreateInstance(t,
    BindingFlags.CreateInstance | BindingFlags.Public | BindingFlags.Instance | BindingFlags.OptionalParamBinding, null, [], null)!;

record Group(string Id, IPersonalTable Table, Type Blank, string[] Versions, bool Other);
