--
-- PostgreSQL database dump
--

\restrict IrV9uLJrzbMevghpDw9IbwaeybDd9rrsIkgq9pdX45bvYnoPUEcalcuZYam09m0

-- Dumped from database version 17.10 (Debian 17.10-1.pgdg13+1)
-- Dumped by pg_dump version 17.10 (Debian 17.10-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: usage; Type: TABLE; Schema: public; Owner: user
--

CREATE TABLE public.usage (
    id integer NOT NULL,
    source text,
    model text,
    prompt_token_count integer,
    candidates_token_count integer,
    total_token_count integer,
    cached_content_token_count integer,
    thoughts_token_count integer,
    cost_usd numeric(12,8),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.usage OWNER TO "user";

--
-- Name: usage_id_seq; Type: SEQUENCE; Schema: public; Owner: user
--

CREATE SEQUENCE public.usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usage_id_seq OWNER TO "user";

--
-- Name: usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: user
--

ALTER SEQUENCE public.usage_id_seq OWNED BY public.usage.id;


--
-- Name: usage id; Type: DEFAULT; Schema: public; Owner: user
--

ALTER TABLE ONLY public.usage ALTER COLUMN id SET DEFAULT nextval('public.usage_id_seq'::regclass);


--
-- Data for Name: usage; Type: TABLE DATA; Schema: public; Owner: user
--

COPY public.usage (id, source, model, prompt_token_count, candidates_token_count, total_token_count, cached_content_token_count, thoughts_token_count, cost_usd, created_at) FROM stdin;
1	rag	gemma-4-31b-it	1300	251	1810	0	259	0.00000000	2026-07-27 16:10:51.325005
2	rag	gemma-4-31b-it	1300	403	2008	0	305	0.00000000	2026-07-27 16:19:03.311995
3	rag	gemini-3.1-flash-lite	1141	27	1168	0	0	0.00032575	2026-07-27 22:40:40.380947
4	rag	gemini-3.1-flash-lite	2101	202	2303	0	0	0.00082825	2026-07-27 22:40:40.404932
5	rag	gemini-3.1-flash-lite	1124	28	1152	0	0	0.00032300	2026-07-27 22:53:56.292837
6	rag	gemini-3.1-flash-lite	2042	195	2237	0	0	0.00080300	2026-07-27 22:53:56.339243
7	rag	gemini-3.1-flash-lite	2490	35	2525	0	0	0.00067500	2026-07-27 22:55:28.108805
8	rag	gemini-3.1-flash-lite	3110	71	3181	0	0	0.00088400	2026-07-27 22:55:28.154991
9	rag	gemini-3.1-flash-lite	3704	32	3736	0	0	0.00097400	2026-07-27 22:56:11.914224
10	rag	gemini-3.1-flash-lite	4679	56	4735	0	0	0.00125375	2026-07-27 22:56:12.004403
11	rag	gemini-3.1-flash-lite	5078	26	5104	0	0	0.00130850	2026-07-27 22:56:53.504457
12	rag	gemini-3.1-flash-lite	5915	147	6062	0	0	0.00169925	2026-07-27 22:56:53.54992
13	rag	gemini-3.1-flash-lite	6553	26	6579	3984	0	0.00167725	2026-07-27 22:58:12.013875
14	rag	gemini-3.1-flash-lite	7441	138	7579	4034	0	0.00206725	2026-07-27 22:58:12.033414
15	rag	gemini-3.1-flash-lite	1073	27	1100	0	0	0.00030875	2026-07-27 22:59:22.310682
16	rag	gemini-3.1-flash-lite	1220	55	1275	0	0	0.00038750	2026-07-27 22:59:22.326044
17	rag	gemini-3.1-flash-lite	1787	29	1816	0	0	0.00049025	2026-07-27 23:00:00.956211
18	rag	gemini-3.1-flash-lite	2007	299	2306	0	0	0.00095025	2026-07-27 23:00:00.971443
19	rag	gemini-3.1-flash-lite	1099	28	1127	0	0	0.00031675	2026-07-27 23:23:02.263057
20	rag	gemini-3.1-flash-lite	2376	44	2420	0	0	0.00066000	2026-07-27 23:23:02.280755
21	rag	gemini-3.1-flash-lite	2725	28	2753	0	0	0.00072325	2026-07-27 23:24:38.888007
22	rag	gemini-3.1-flash-lite	2871	281	3152	0	0	0.00113925	2026-07-27 23:24:38.90456
23	rag	gemini-3.1-flash-lite	1086	28	1114	0	0	0.00031350	2026-07-27 23:28:58.830508
24	rag	gemini-3.1-flash-lite	1372	285	1657	0	0	0.00077050	2026-07-27 23:28:58.846826
25	rag	gemini-3.1-flash-lite	2173	24	2197	0	0	0.00057925	2026-07-27 23:30:53.665217
26	rag	gemini-3.1-flash-lite	2549	44	2593	0	0	0.00070325	2026-07-27 23:30:53.681977
27	rag	gemini-3.1-flash-lite	2813	25	2838	0	0	0.00074075	2026-07-28 13:39:58.629176
28	rag	gemini-3.1-flash-lite	3000	136	3136	0	0	0.00095400	2026-07-28 13:39:58.674289
29	rag	gemini-3.1-flash-lite	3655	29	3684	0	0	0.00095725	2026-07-28 13:41:20.733754
30	rag	gemini-3.1-flash-lite	3947	181	4128	0	0	0.00125825	2026-07-28 13:41:20.746669
31	rag	gemini-3.1-flash-lite	4646	26	4672	0	0	0.00120050	2026-07-28 13:42:40.017994
32	rag	gemini-3.1-flash-lite	5072	77	5149	0	0	0.00138350	2026-07-28 13:42:40.062767
33	rag	gemini-3.1-flash-lite	1132	33	1165	0	0	0.00033250	2026-07-28 13:46:52.323993
34	rag	gemini-3.1-flash-lite	1397	36	1433	0	0	0.00040325	2026-07-28 13:46:52.342892
35	rag	gemini-3.1-flash-lite	1656	31	1687	0	0	0.00046050	2026-07-28 13:49:38.056592
36	rag	gemini-3.1-flash-lite	1660	36	1696	0	0	0.00046900	2026-07-28 13:49:38.073166
37	rag	gemini-3.1-flash-lite	2227	31	2258	0	0	0.00060325	2026-07-28 13:49:38.087272
38	rag	gemini-3.1-flash-lite	2209	20	2229	0	0	0.00058225	2026-07-28 13:49:38.100785
39	rag	gemini-3.1-flash-lite	2767	32	2799	0	0	0.00073975	2026-07-28 13:50:54.707115
40	rag	gemini-3.1-flash-lite	3065	38	3103	0	0	0.00082325	2026-07-28 13:50:54.752825
41	rag	gemini-3.1-flash-lite	1119	30	1149	0	0	0.00032475	2026-07-28 13:57:26.561252
42	rag	gemini-3.1-flash-lite	1975	118	2093	0	0	0.00067075	2026-07-28 13:57:26.569235
43	rag	gemini-3.1-flash-lite	2622	30	2652	0	0	0.00070050	2026-07-28 13:59:00.879607
44	rag	gemini-3.1-flash-lite	4417	108	4525	0	0	0.00126625	2026-07-28 13:59:00.90151
45	rag	gemini-3.1-flash-lite	4600	33	4633	0	0	0.00119950	2026-07-28 14:01:16.076827
46	rag	gemini-3.1-flash-lite	5378	127	5505	0	0	0.00153500	2026-07-28 14:01:16.123593
47	rag	gemini-3.1-flash-lite	1081	28	1109	0	0	0.00031225	2026-07-28 14:51:42.378583
48	rag	gemini-3.1-flash-lite	2087	91	2178	0	0	0.00065825	2026-07-28 14:51:42.391538
49	rag	gemini-3.1-flash-lite	1118	26	1144	0	0	0.00031850	2026-07-28 14:55:04.402847
50	rag	gemini-3.1-flash-lite	1731	61	1792	0	0	0.00052425	2026-07-28 14:55:04.421824
51	rag	gemini-3.1-flash-lite	1071	27	1098	0	0	0.00030825	2026-07-28 15:06:49.629637
52	rag	gemini-3.1-flash-lite	1223	235	1458	0	0	0.00065825	2026-07-28 15:06:49.64839
53	rag	gemini-3.1-flash-lite	1082	26	1108	0	0	0.00030950	2026-07-28 15:11:20.29074
54	rag	gemini-3.1-flash-lite	1312	282	1594	0	0	0.00075100	2026-07-28 15:11:20.337106
55	rag	gemini-3.1-flash-lite	2106	30	2136	0	0	0.00057150	2026-07-28 15:13:43.525644
56	rag	gemini-3.1-flash-lite	2306	139	2445	0	0	0.00078500	2026-07-28 15:13:43.541774
57	rag	gemini-3.1-flash-lite	1101	40	1141	0	0	0.00033525	2026-07-28 15:33:03.217974
58	rag	gemini-3.1-flash-lite	1937	127	2064	0	0	0.00067475	2026-07-28 15:33:03.234186
59	rag	gemini-3.1-flash-lite	2624	30	2654	0	0	0.00070100	2026-07-28 15:37:30.238696
60	rag	gemini-3.1-flash-lite	3175	54	3229	0	0	0.00087475	2026-07-28 15:37:30.25508
61	rag	gemini-3.1-flash-lite	1097	26	1123	0	0	0.00031325	2026-07-28 15:40:16.452139
62	rag	gemini-3.1-flash-lite	2289	99	2388	0	0	0.00072075	2026-07-28 15:40:16.468105
63	rag	gemini-3.1-flash-lite	2908	28	2936	0	0	0.00076900	2026-07-28 15:53:38.122039
64	rag	gemini-3.1-flash-lite	3633	106	3739	0	0	0.00106725	2026-07-28 15:53:38.139428
65	rag	gemma-4-26b-a4b-it	1370	25	1395	0	0	0.00000000	2026-07-28 16:16:32.38076
66	rag	gemma-4-26b-a4b-it	2966	43	3095	0	86	0.00000000	2026-07-28 16:16:32.388669
\.


--
-- Name: usage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: user
--

SELECT pg_catalog.setval('public.usage_id_seq', 66, true);


--
-- Name: usage usage_pkey; Type: CONSTRAINT; Schema: public; Owner: user
--

ALTER TABLE ONLY public.usage
    ADD CONSTRAINT usage_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict IrV9uLJrzbMevghpDw9IbwaeybDd9rrsIkgq9pdX45bvYnoPUEcalcuZYam09m0

