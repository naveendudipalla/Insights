package com.cognizant.devops.platformservice.webhook.service;

import java.util.ArrayList;
import java.util.List;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;

import com.cognizant.devops.platformcommons.exception.InsightsCustomException;
import com.cognizant.devops.platformdal.webhookConfig.WebHookConfig;
import com.cognizant.devops.platformdal.webhookConfig.WebHookConfigDAL;

@Service("webhookConfigurationService")
public class WebHookService implements IWebHook {
	private static final Logger log = LogManager.getLogger(WebHookService.class);
	private static final String SUCCESS = "SUCCESS";
	// @Override

	public Boolean saveWebHookConfiguration(String webhookname, String toolName, String eventname, String dataformat,
			String mqchannel, Boolean subscribestatus) {

		WebHookConfig webHookConfig = populateWebHookConfiguration(webhookname, toolName, eventname, dataformat,
				mqchannel, subscribestatus);

		log.error(webHookConfig.getDataFormat());
		log.error(webHookConfig.getEventName());
		log.error(webHookConfig.getWebHookName());
		log.error(webHookConfig.getMQChannel());
		log.error(webHookConfig.getSubscribeStatus());
		WebHookConfigDAL webhookConfigurationDAL = new WebHookConfigDAL();

		return webhookConfigurationDAL.saveWebHookConfiguration(webHookConfig);

	}

	public List<WebHookConfigTO> getRegisteredWebHooks() throws InsightsCustomException {
		WebHookConfigDAL webhookConfigDAL = new WebHookConfigDAL();
		List<WebHookConfigTO> webhookList = null;
		try {
			List<WebHookConfig> webhookConfigList = webhookConfigDAL.getAllWebHookConfigurations();
			webhookList = new ArrayList<>(webhookConfigList.size());
			for (WebHookConfig webhookConfig : webhookConfigList) {
				WebHookConfigTO to = new WebHookConfigTO();
				BeanUtils.copyProperties(webhookConfig, to, new String[] { "agentJson", "updatedDate" });
				webhookList.add(to);
			}
		} catch (Exception e) {
			log.error("Error getting all webhook config", e);
			throw new InsightsCustomException(e.toString());
		}

		return webhookList;
	}

	public WebHookConfig loadWebHookConfiguration(String webhookName) {
		WebHookConfigDAL webhookConfigurationDAL = new WebHookConfigDAL();
		return webhookConfigurationDAL.loadWebHookConfiguration(webhookName);
	}

	private WebHookConfig populateWebHookConfiguration(String webhookname, String toolName, String eventname,
			String dataformat, String mqchannel, Boolean subscribestatus) {
		WebHookConfig webhookConfiguration = new WebHookConfig();

		// String updatedSettingsJson = updateNextRunTimeValue(settingsJson);
		webhookConfiguration.setDataFormat(dataformat);
		webhookConfiguration.setEventName(eventname);
		webhookConfiguration.setToolName(toolName);
		;
		webhookConfiguration.setMQChannel(mqchannel);
		webhookConfiguration.setWebHookName(webhookname);
		webhookConfiguration.setSubscribeStatus(subscribestatus);
		return webhookConfiguration;
	}

	public String uninstallWebhook(String webhookname) throws InsightsCustomException {
		try {

			WebHookConfigDAL webhookConfigDAL = new WebHookConfigDAL();
			webhookConfigDAL.deleteWebhookConfigurations(webhookname);
		} catch (Exception e) {
			log.error("Error while un-installing webhook..", e);
			throw new InsightsCustomException(e.toString());
		}

		return SUCCESS;
	}

	public String updateWebHook(String webhookname, String toolName, String eventname, String dataformat,
			String mqchannel, Boolean subscribestatus) throws InsightsCustomException {
		Boolean status;
		try {

			status = saveWebHookConfiguration(webhookname, toolName, eventname, dataformat, mqchannel, subscribestatus);

		} catch (Exception e) {
			log.error("Error updating the webhook", e);
			throw new InsightsCustomException(e.toString());
		}

		return SUCCESS;
	}

}
