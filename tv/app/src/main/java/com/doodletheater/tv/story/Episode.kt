package com.doodletheater.tv.story

import org.json.JSONObject

/** A stage direction: [who] does [act] at the start of a beat, or when [atWord] is spoken. */
data class Action(val who: String, val act: String, val atWord: String?)

data class Beat(val speaker: String, val text: String, val actions: List<Action>, val audio: String?, val marks: List<Mark>)

/** Polly speech mark: word [start, end) in the text is spoken at [timeMs]. */
data class Mark(val timeMs: Long, val start: Int, val end: Int)

/** A choice button; [emoji] is the picture that lets pre-readers pick (blank on older episodes). */
data class Option(val label: String, val next: String, val emoji: String = "")
data class Choice(val prompt: String, val options: List<Option>)
data class Scene(val id: String, val backdrop: String, val beats: List<Beat>, val choice: Choice?)
data class Star(val id: String, val name: String, val pitch: Float)

/** The branching play the server wrote (see server/doodle_theater/story/schema.py). */
data class Episode(val id: String, val title: String, val theme: String, val cast: List<Star>, val scenes: Map<String, Scene>) {
    companion object {
        fun parse(json: String): Episode {
            val o = JSONObject(json)
            val sc = o.getJSONObject("scenes")
            val scenes = sc.keys().asSequence().associateWith { id ->
                val s = sc.getJSONObject(id)
                val beats = s.getJSONArray("beats").let { arr ->
                    (0 until arr.length()).map { i ->
                        val b = arr.getJSONObject(i)
                        val acts = b.optJSONArray("actions")
                        val marks = b.optJSONArray("marks")
                        Beat(
                            speaker = b.optString("speaker", "narrator"),
                            text = b.getString("text"),
                            actions = (0 until (acts?.length() ?: 0)).map { k ->
                                val a = acts!!.getJSONObject(k)
                                Action(a.getString("who"), a.getString("do"),
                                    if (a.has("at_word")) a.getString("at_word") else null)
                            },
                            audio = if (b.has("audio")) b.getString("audio") else null,
                            marks = (0 until (marks?.length() ?: 0)).map { k ->
                                val m = marks!!.getJSONObject(k)
                                Mark(m.getLong("time"), m.getInt("start"), m.getInt("end"))
                            },
                        )
                    }
                }
                val choice = s.optJSONObject("choice")?.let { c ->
                    val opts = c.getJSONArray("options")
                    Choice(c.optString("prompt", "What should they do?"),
                        (0 until opts.length()).map {
                            val op = opts.getJSONObject(it)
                            Option(op.getString("label"), op.getString("next"), op.optString("emoji", ""))
                        })
                }
                Scene(id, s.getString("backdrop"), beats, choice)
            }
            val castArr = o.getJSONArray("cast")
            val cast = (0 until castArr.length()).map {
                val c = castArr.getJSONObject(it)
                Star(c.getString("id"), c.getString("name"), c.optDouble("pitch", 1.3).toFloat())
            }
            return Episode(o.getString("id"), o.getString("title"), o.getString("theme"), cast, scenes)
        }
    }
}
