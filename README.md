<h1 align="center">
<!-- 	<img width="300" src="https://github.com/gCBS/gCBS_native/blob/stable/assets/gCBSColorPurp@3x.png?raw=true" alt="gCBS"> -->
      Chowkidaar | Discord Monitoring Bot
	<br>
</h1>


<div align="center">

Chowkidaar monitors the student activities during the 45 Days of Productivity - A PSoc Initiative.

<h3>P-Society Handles</h3>
<h3 align="center">
	<a href="https://dev-psoc.netlify.app/">Website</a>
	<span> | </span>
	<a href="https://discord.gg/5Tj7DEED">Community Discord</a>
	<span> | </span>
	<a href="https://github.com/gCBS/gCBS/projects?type=classic">Contribute</a>
</h3>

</div>

----------------------------------------
<div align="center">

**Chowkidaar** is a Automation & Monitoring Discord Bot. The application is built using Python,PostgreSQL.
</div>
<div align="center">
<br/>
<img src='https://skillicons.dev/icons?i=py,postgresql' ></img>

</div>
<br/>

## Getting Started

To run the bot locally, follow these steps:

1. **Install `uv`** (an extremely fast Python package installer and resolver):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. **Environment Setup**:
   Create your environment file by copying the provided example:
   ```bash
   cp .env.example .env.local
   ```
   Open `.env.local` and add your specific `DISCORD_TOKEN` and `WATCHED_CHANNEL_ID`.
3. **Start the database** (using Docker Compose):
   Ensure you have Docker installed and running, then start the PostgreSQL database:
   ```bash
   sudo docker compose up -d
   ```
4. **Initialize the Database (First-time setup only)**:
   Wait ~10 seconds for the PostgreSQL container to fully start up, then run the initialization script to create the required tables (`student_list_2024`, `participation_logs`, etc.):
   ```bash
   uv run --python 3.12 scripts/init_db.py
   ```
5. **Run the bot**:
   ```bash
   uv run --python 3.12 main.py
   ```

## Maintenance & Configuration

To update the bot's content for a new year or season, you will need to modify the following JSON configuration files located in the `configs/` directory. You do not need to edit any Python code!

*   **`configs/event_config.json`**: Edit this to change the `start_date`, the `duration_days` of the event, and the template text for daily announcements.
*   **`configs/questions.json`**: This JSON file maps the Day number to the specific LeetCode/CodeForces questions required for that day.
*   **`configs/dev.json`**: This JSON file contains the daily resource links and descriptions sent to the Development channel.

<!--
Coupon Aggregator offers two primary benefits to its users. 

- Real-time listing and count of available coupons.
- Supply and demand of coupons currently in circulation.
-->

### Current contributors <a name="Current contributors"></a>

<a href="https://github.com/p-society/chowkidaar/graphs/contributors">
  <img src="https://contributors-img.web.app/image?repo=p-society/chowkidaar" />
</a>

Made with [contributors-img](https://contributors-img.web.app).

<!--
## Subscribe to updates
<!--
Join our [Discord Server](https://gCBS.com/joincommunity) and subscribe to this repository[Developer Newsletter](https://gCBS.com/newsletter/?utm_medium=community&utm_source=github&utm_campaign=gCBS%20repo) to get updates, information about gCBS 
-->
# License <a name="License"></a>

PSoc/Chowkidaar is licensed under [GPL-3.0 License](https://github.com/p-society/chowkidaar/blob/main/LICENSE)
